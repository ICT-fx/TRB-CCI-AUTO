"""L'unique appel Claude. Reçoit un document, renvoie un OrderExtraction typé.

Utilise un forced tool call : la réponse est toujours un bloc tool_use dont
`input` est le JSON structuré. `_normalize()` garantit un objet bien formé même
si le modèle omet des champs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Union

from anthropic import Anthropic

from . import config
from .models import OrderExtraction, ProductLine
from .schema import EXTRACT_ORDER_TOOL, EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# --- Source de document acceptée par Claude vision -----------------------
@dataclass
class PdfSource:
    base64_data: str
    kind: Literal["pdf"] = "pdf"


@dataclass
class ImageSource:
    base64_data: str
    media_type: Literal["image/png", "image/jpeg"]
    kind: Literal["image"] = "image"


DocumentSource = Union[PdfSource, ImageSource]


class ClaudeError(RuntimeError):
    """Réponse Claude inattendue (refus, pas de tool_use, etc.)."""


class ApiKeyMissingError(RuntimeError):
    """ANTHROPIC_API_KEY absente de l'environnement."""


# Client réutilisé entre invocations (les workers Azure restent chauds).
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ApiKeyMissingError(
            "ANTHROPIC_API_KEY n'est pas définie. Ajoute-la dans local.settings.json "
            "(local) ou dans les Application Settings de la Function App (Azure)."
        )
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _build_content_block(source: DocumentSource) -> dict:
    if isinstance(source, PdfSource):
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": source.base64_data,
            },
        }
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": source.media_type,
            "data": source.base64_data,
        },
    }


def extract_order(source: DocumentSource) -> OrderExtraction:
    """Envoie un document à Claude et renvoie l'extraction structurée."""
    client = _get_client()

    logger.info("Appel Claude (modèle=%s)…", config.ANTHROPIC_MODEL)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=EXTRACTION_SYSTEM_PROMPT,
        tools=[EXTRACT_ORDER_TOOL],
        tool_choice={"type": "tool", "name": "extract_order"},
        messages=[
            {
                "role": "user",
                "content": [
                    _build_content_block(source),
                    {
                        "type": "text",
                        "text": "Extrais toutes les informations de commande de ce document via l'outil extract_order.",
                    },
                ],
            }
        ],
    )

    tool_use = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use is None:
        if response.stop_reason == "refusal":
            raise ClaudeError("La requête a été refusée par le système de sécurité.")
        raise ClaudeError("Claude n'a pas renvoyé de données structurées pour ce document.")

    return _normalize(tool_use.input)


def _coerce_number(value) -> float | None:
    """Renvoie un float si possible (0 conservé), sinon None."""
    if isinstance(value, bool):  # bool est sous-classe d'int : à exclure
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize(raw: dict) -> OrderExtraction:
    """Normalisation défensive : un objet bien formé est toujours renvoyé."""
    raw = raw or {}

    raw_products = raw.get("products")
    products: list[ProductLine] = []
    if isinstance(raw_products, list):
        for p in raw_products:
            p = p or {}
            products.append(
                ProductLine(
                    sku=p.get("sku"),
                    quantity=_coerce_number(p.get("quantity")),
                )
            )

    confidence = _coerce_number(raw.get("confidence"))
    confidence = 0.0 if confidence is None else max(0.0, min(1.0, confidence))

    return OrderExtraction(
        customer_name=raw.get("customer_name"),
        partner_reference=raw.get("partner_reference"),
        requested_delivery_date=raw.get("requested_delivery_date"),
        products=products,
        comments=raw.get("comments"),
        confidence=confidence,
        # is_readable : on ne considère illisible que si explicitement False.
        is_readable=raw.get("is_readable") is not False,
        quality_note=raw.get("quality_note"),
    )

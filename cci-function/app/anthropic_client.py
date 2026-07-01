"""L'unique appel Claude. Reçoit un document, renvoie un OrderExtraction typé.

Utilise un forced tool call : la réponse est toujours un bloc tool_use dont
`input` est le JSON structuré. `_normalize()` garantit un objet bien formé même
si le modèle omet des champs.
"""

from __future__ import annotations

import datetime
import logging
import re
from dataclasses import dataclass
from typing import Literal, Union

from anthropic import Anthropic

from . import config
from .models import OrderExtraction, ProductLine
from .schema import (
    EXTRACT_ORDER_TOOL,
    EXTRACTION_SYSTEM_PROMPT,
    RESOLUTION_SYSTEM_PROMPT,
    RESOLVE_ORDER_TOOL,
)

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


def _render_order_for_resolution(order: OrderExtraction) -> str:
    """Sérialise la commande extraite pour le 2e appel (résolution)."""
    lines = []
    for i, p in enumerate(order.products, start=1):
        des = p.designation or "(désignation absente)"
        sku = p.sku if p.sku else "(aucun SKU)"
        lines.append(f'{i}. désignation="{des}", sku="{sku}", quantité={p.quantity}')
    lignes = "\n".join(lines) if lines else "(aucune ligne produit)"
    return (
        f'Nom du client sur la commande : "{order.customer_name or ""}"\n\n'
        f"Lignes produit (garde le même ordre dans ta réponse) :\n{lignes}"
    )


def resolve_order(order: OrderExtraction, master_context: str) -> dict:
    """2e appel Claude : relie la commande à la master data.

    `master_context` (clients + catalogues) est envoyé en bloc système mis en
    CACHE : stable d'un document à l'autre, il n'est facturé plein tarif qu'une
    fois par lot. Renvoie le dict brut de l'outil resolve_order.
    """
    client = _get_client()

    logger.info("Appel Claude résolution (modèle=%s)…", config.ANTHROPIC_MODEL)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=[
            {"type": "text", "text": RESOLUTION_SYSTEM_PROMPT},
            # Master data volumineuse et stable -> cache éphémère (réutilisé dans le lot).
            {"type": "text", "text": master_context, "cache_control": {"type": "ephemeral"}},
        ],
        tools=[RESOLVE_ORDER_TOOL],
        tool_choice={"type": "tool", "name": "resolve_order"},
        messages=[{"role": "user", "content": _render_order_for_resolution(order)}],
    )

    tool_use = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use is None:
        if response.stop_reason == "refusal":
            raise ClaudeError("La résolution a été refusée par le système de sécurité.")
        raise ClaudeError("Claude n'a pas renvoyé de résolution structurée.")
    return tool_use.input or {}


def _first_business_day(year: int, month: int) -> datetime.date:
    """1er jour du mois, décalé au lundi si c'est un samedi/dimanche."""
    d = datetime.date(year, month, 1)
    while d.weekday() >= 5:  # 5 = samedi, 6 = dimanche
        d += datetime.timedelta(days=1)
    return d


def _format_delivery_date(raw) -> str | None:
    """Normalise la date de livraison au format strict JJ/MM/AAAA.

    - AAAA-MM-JJ  -> JJ/MM/AAAA
    - AAAA-MM     -> 1er jour ouvré du mois, au format JJ/MM/AAAA
    - JJ/MM/AAAA  -> inchangé
    - autre       -> renvoyé tel quel (dernier recours)
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, dd = (int(x) for x in m.groups())
        try:
            return datetime.date(y, mo, dd).strftime("%d/%m/%Y")
        except ValueError:
            return s
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        y, mo = (int(x) for x in m.groups())
        try:
            return _first_business_day(y, mo).strftime("%d/%m/%Y")
        except ValueError:
            return s
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        return s
    return s


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
                    designation=p.get("designation"),
                    sku=p.get("sku"),
                    quantity=_coerce_number(p.get("quantity")),
                )
            )

    confidence = _coerce_number(raw.get("confidence"))
    confidence = 0.0 if confidence is None else max(0.0, min(1.0, confidence))

    return OrderExtraction(
        customer_name=raw.get("customer_name"),
        partner_reference=raw.get("partner_reference"),
        requested_delivery_date=_format_delivery_date(raw.get("requested_delivery_date")),
        products=products,
        comments=raw.get("comments"),
        confidence=confidence,
        # is_readable : on ne considère illisible que si explicitement False.
        is_readable=raw.get("is_readable") is not False,
        quality_note=raw.get("quality_note"),
    )

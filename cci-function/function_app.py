"""Azure Function HTTP : document de commande -> Excel CCI.

Flux (un document par requête) :
  1. lire le fichier reçu dans le corps de la requête
  2. détecter le type (PDF / PNG / JPEG / TIFF) ; convertir TIFF -> PNG
  3. extraire les données via Claude (forced tool call)
  4. enrichir via le master data (client -> TVA, monnaie, incoterm…)
  5. générer l'Excel avec openpyxl (format forcé)
  6. renvoyer le .xlsx en corps de réponse

Toutes les étapes sont loggées. Les erreurs renvoient un JSON propre (jamais de
stack trace au client).
"""

from __future__ import annotations

import base64
import io
import json
import logging
from datetime import datetime, timezone

import azure.functions as func

from app import enrichment
from app.anthropic_client import (
    ApiKeyMissingError,
    ClaudeError,
    ImageSource,
    PdfSource,
    extract_order,
)
from app.excel_writer import build_workbook

logger = logging.getLogger("cci")

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _json_error(message: str, status: int, *, file_name: str | None = None, **extra) -> func.HttpResponse:
    payload = {"error": message}
    if file_name is not None:
        payload["fichier"] = file_name
    payload.update(extra)
    logger.warning("Réponse erreur %s : %s", status, message)
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
    )


def _detect_kind(body: bytes, content_type: str | None, file_name: str) -> str | None:
    """Renvoie 'pdf' | 'png' | 'jpeg' | 'tiff' ou None si non supporté.

    Combine en-tête Content-Type, extension du nom de fichier, puis octets
    magiques en dernier recours.
    """
    ct = (content_type or "").lower()
    name = (file_name or "").lower()

    if "pdf" in ct or name.endswith(".pdf"):
        return "pdf"
    if "png" in ct or name.endswith(".png"):
        return "png"
    if "jpeg" in ct or "jpg" in ct or name.endswith((".jpg", ".jpeg")):
        return "jpeg"
    if "tiff" in ct or name.endswith((".tif", ".tiff")):
        return "tiff"

    # Derniers recours : octets magiques.
    if body[:4] == b"%PDF":
        return "pdf"
    if body[:4] == b"\x89PNG":
        return "png"
    if body[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if body[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    return None


def _tiff_to_png(body: bytes) -> bytes:
    """Convertit un TIFF en PNG (Claude vision n'accepte pas le TIFF)."""
    from PIL import Image

    with Image.open(io.BytesIO(body)) as img:
        out = io.BytesIO()
        img.convert("RGB").save(out, format="PNG")
        return out.getvalue()


@app.route(route="extract", methods=["POST"])
def extract(req: func.HttpRequest) -> func.HttpResponse:
    # Nom du fichier : query ?filename= en priorité, sinon Content-Disposition.
    file_name = req.params.get("filename") or "document"

    body = req.get_body()
    logger.info("Requête reçue : fichier=%r, taille=%d octets", file_name, len(body or b""))

    if not body:
        return _json_error("Corps de requête vide : aucun fichier reçu.", 400, file_name=file_name)

    kind = _detect_kind(body, req.headers.get("Content-Type"), file_name)
    if kind is None:
        return _json_error(
            "Type de fichier non supporté (attendu : PDF, PNG, JPEG ou TIFF).",
            400,
            file_name=file_name,
        )

    # Construire la source pour Claude (conversion TIFF -> PNG si besoin).
    try:
        if kind == "pdf":
            source = PdfSource(base64_data=base64.b64encode(body).decode("ascii"))
        else:
            if kind == "tiff":
                logger.info("Conversion TIFF -> PNG…")
                body = _tiff_to_png(body)
                media_type = "image/png"
            else:
                media_type = "image/png" if kind == "png" else "image/jpeg"
            source = ImageSource(
                base64_data=base64.b64encode(body).decode("ascii"),
                media_type=media_type,
            )
    except Exception:
        logger.exception("Échec de la lecture / conversion du fichier.")
        return _json_error("Fichier illisible ou corrompu.", 400, file_name=file_name)

    # Extraction Claude.
    try:
        order = extract_order(source)
    except ApiKeyMissingError as exc:
        return _json_error(str(exc), 500, file_name=file_name)
    except ClaudeError as exc:
        return _json_error(str(exc), 502, file_name=file_name)
    except Exception:
        logger.exception("Erreur inattendue pendant l'extraction.")
        return _json_error("Erreur interne pendant l'extraction.", 500, file_name=file_name)

    logger.info(
        "Extraction OK : client=%r, %d produit(s), confiance=%.2f, lisible=%s",
        order.customer_name, len(order.products), order.confidence, order.is_readable,
    )

    # Document jugé illisible par Claude -> erreur identifiant le fichier.
    if not order.is_readable:
        return _json_error(
            "Document jugé illisible par l'extraction — à router vers revue manuelle.",
            422,
            file_name=file_name,
            confiance=round(order.confidence, 2),
            note_qualite=order.quality_note,
        )

    # Enrichissement master data (jointure sur le client).
    try:
        master = enrichment.enrich(order)
    except Exception:
        logger.exception("Erreur pendant l'enrichissement master data.")
        return _json_error("Erreur interne pendant l'enrichissement.", 500, file_name=file_name)

    # Génération de l'Excel.
    try:
        xlsx_bytes = build_workbook(order, master, file_name)
    except Exception:
        logger.exception("Erreur pendant la génération de l'Excel.")
        return _json_error("Erreur interne pendant la génération de l'Excel.", 500, file_name=file_name)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_name = f"CCI-{stamp}.xlsx"
    logger.info("Réponse 200 : %s (%d octets)", out_name, len(xlsx_bytes))

    return func.HttpResponse(
        body=xlsx_bytes,
        status_code=200,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )

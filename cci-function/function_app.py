"""Azure Functions HTTP : extraction de commande + génération Excel CCI consolidé.

Deux routes (auth FUNCTION) :

  POST /api/extract  — un document par requête
    1. lire le fichier reçu dans le corps de la requête
    2. détecter le type (PDF / PNG / JPEG / TIFF) ; convertir TIFF -> PNG
    3. extraire les données via Claude (forced tool call)
    4. valider le format de la commande (sinon 422 « A-revoir »)
    5. résoudre via le master data (Claude) : code Customer « Clé 1 » +
       validation/correction du SKU de chaque ligne via le catalogue du client
    6. valider strictement le résultat : client introuvable ou produit hors
       catalogue -> 422 « A-revoir »
    7. renvoyer un record JSON (200) consommé par le Logic App

  POST /api/build  — agrège plusieurs records en un seul Excel
    Entrée : {"rows": [<record>, …]} ; sortie : .xlsx consolidé (1 ligne/record).

Toutes les étapes sont loggées. Les erreurs renvoient un JSON propre (jamais de
stack trace au client).
"""

from __future__ import annotations

import base64
import io
import json
import logging

import azure.functions as func

from app import resolver
from app.anthropic_client import (
    ApiKeyMissingError,
    ClaudeError,
    ImageSource,
    PdfSource,
    extract_order,
)
from app.excel_writer import build_consolidated_workbook
from app.models import build_record, validate_order, validate_resolution

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

    # Validation de FORMAT (avant résolution). Le SKU n'est pas gaté ici : il
    # peut être faux/absent et sera corrigé via le catalogue à la résolution.
    reasons = validate_order(order)
    if reasons:
        raison = " ; ".join(reasons)
        return _json_error(
            "Commande à router vers revue manuelle (A-revoir).",
            422,
            file_name=file_name,
            raison=raison,
            confiance=round(order.confidence, 2),
            note_qualite=order.quality_note,
        )

    # Résolution master data (Claude) : retrouve le code Customer (Clé 1) et
    # valide/corrige le SKU de chaque ligne via le catalogue du client.
    try:
        resolution = resolver.resolve(order)
    except ApiKeyMissingError as exc:
        return _json_error(str(exc), 500, file_name=file_name)
    except ClaudeError as exc:
        return _json_error(str(exc), 502, file_name=file_name)
    except Exception:
        logger.exception("Erreur pendant la résolution master data.")
        return _json_error("Erreur interne pendant la résolution.", 500, file_name=file_name)

    # Validation stricte APRÈS résolution : client introuvable OU produit hors
    # catalogue du client -> A-revoir (422), routé vers revue manuelle.
    reasons = validate_resolution(order, resolution)
    if reasons:
        raison = " ; ".join(reasons)
        return _json_error(
            "Commande à router vers revue manuelle (A-revoir).",
            422,
            file_name=file_name,
            raison=raison,
            confiance=round(order.confidence, 2),
            note_qualite=order.quality_note,
        )

    # Construire le record JSON (contrat consommé par le Logic App et /api/build).
    record = build_record(order, resolution, file_name)
    logger.info(
        "Réponse 200 (record) : client=%r, Clé 1=%s, statut=%r",
        record["customer_name"], record["customer_code"], resolution.status,
    )
    return func.HttpResponse(
        json.dumps(record, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="build", methods=["POST"])
def build(req: func.HttpRequest) -> func.HttpResponse:
    """Agrège des records (issus de /api/extract) en un seul Excel consolidé.

    Entrée : {"rows": [<record>, …]}. Sortie : .xlsx (1 ligne par record).
    `rows` manquant -> 400. `rows` = [] -> classeur valide avec seulement l'en-tête.
    """
    try:
        payload = req.get_json()
    except ValueError:
        return _json_error("Corps JSON invalide : objet {\"rows\": [...]} attendu.", 400)

    if not isinstance(payload, dict) or "rows" not in payload:
        return _json_error("Champ 'rows' manquant dans le corps JSON.", 400)

    rows = payload.get("rows")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        return _json_error("Le champ 'rows' doit être une liste de records.", 400)

    logger.info("Build consolidé : %d record(s).", len(rows))

    try:
        xlsx_bytes = build_consolidated_workbook(rows)
    except Exception:
        logger.exception("Erreur pendant la génération de l'Excel consolidé.")
        return _json_error("Erreur interne pendant la génération de l'Excel.", 500)

    out_name = "CCI-Lot.xlsx"
    logger.info("Réponse 200 : %s (%d octets)", out_name, len(xlsx_bytes))
    return func.HttpResponse(
        body=xlsx_bytes,
        status_code=200,
        mimetype=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )

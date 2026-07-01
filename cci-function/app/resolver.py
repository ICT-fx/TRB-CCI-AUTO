"""Résolution master data d'une commande : code Customer (Clé 1) + SKU corrigés.

Orchestration :
  1. charge la master data (enrichment.get_store()) ;
  2. demande à Claude (anthropic_client.resolve_order) de retrouver le client et
     de valider/corriger le SKU de chaque ligne via le catalogue du client ;
  3. RECONTRÔLE la réponse contre la master data (garde-fou anti-hallucination) :
     un code ou un SKU renvoyé par le modèle n'est accepté que s'il existe
     réellement dans la master data.

Le résultat est écrit sur chaque ProductLine (resolved_sku / sku_status) et
résumé par un objet Resolution. La décision de rejet « A-revoir » est prise
ensuite par models.validate_resolution.
"""

from __future__ import annotations

import logging

from . import anthropic_client, enrichment
from .models import OrderExtraction, Resolution

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"ok", "corrige", "ambigu", "inconnu"}


def _s(value) -> str:
    return "" if value is None else str(value).strip()


def resolve(order: OrderExtraction) -> Resolution:
    """Résout la commande contre la master data. Mute order.products en place."""
    store = enrichment.get_store()

    if not store.available:
        logger.warning("Master data indisponible — résolution impossible.")
        for p in order.products:
            p.resolved_sku, p.sku_status = None, "inconnu"
        return Resolution(matched=False, status="master data indisponible")

    raw = anthropic_client.resolve_order(order, store.context)

    # 1) Client — n'accepter qu'un code réellement présent dans la master data.
    code = _s(raw.get("customer_code")) or None
    known = code is not None and store.name_for(code) is not None
    if code is not None and not known:
        logger.warning("Claude a renvoyé un code Customer inconnu (%r) — ignoré.", code)
    matched = known
    resolved_code = code if known else None

    # 2) Lignes — mapping par index, avec garde-fou : un SKU n'est retenu que
    #    s'il appartient vraiment au catalogue du client résolu.
    raw_lines = raw.get("lines")
    raw_lines = raw_lines if isinstance(raw_lines, list) else []

    for i, p in enumerate(order.products):
        li = raw_lines[i] if i < len(raw_lines) else {}
        li = li if isinstance(li, dict) else {}
        resolved_sku = _s(li.get("resolved_sku")) or None
        status = _s(li.get("status")).lower()
        if status not in _VALID_STATUSES:
            status = "inconnu"

        # Garde-fou : sans client résolu, ou si le SKU n'est pas au catalogue du
        # client, la ligne est déclarée inconnue (jamais de SKU inventé).
        if not matched or not resolved_sku or not store.has_sku(resolved_code, resolved_sku):
            p.resolved_sku, p.sku_status = None, "inconnu"
        else:
            p.resolved_sku = resolved_sku
            # Conserver "corrige"/"ambigu" tels quels ; tout le reste devient "ok".
            p.sku_status = status if status in ("corrige", "ambigu") else "ok"

    n_corr = sum(1 for p in order.products if p.sku_status == "corrige")
    n_amb = sum(1 for p in order.products if p.sku_status == "ambigu")
    n_unknown = sum(1 for p in order.products if p.sku_status == "inconnu")
    status = "OK" if matched else "client introuvable"
    if matched:
        parts = []
        if n_corr:
            parts.append(f"{n_corr} SKU corrigé{'s' if n_corr > 1 else ''}")
        if n_amb:
            parts.append(f"{n_amb} à vérifier")
        if parts:
            status = "OK (" + ", ".join(parts) + ")"

    logger.info(
        "Résolution : client_code=%s (matched=%s), %d corrigé(s), %d ambigu(s), %d inconnu(s).",
        resolved_code, matched, n_corr, n_amb, n_unknown,
    )
    return Resolution(
        customer_code=resolved_code,
        customer_name_master=store.name_for(resolved_code),
        matched=matched,
        status=status,
    )

"""Contrat de données partagé par tout le pipeline.

`OrderExtraction` est l'objet pivot : produit par anthropic_client (extraction),
complété par resolver (résolution master data), écrit par excel_writer. Changer un
champ ici impose de toucher le schéma (schema.py) et l'écriture Excel
(excel_writer.py) — commencer par ce fichier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Un SKU valide est un code numérique à exactement 4 chiffres.
_SKU_RE = re.compile(r"^\d{4}$")


@dataclass
class ProductLine:
    """Une ligne produit.

    `designation`, `sku`, `quantity` sont LUS sur le document. `resolved_sku` et
    `sku_status` sont remplis ensuite par la résolution master data :
      - status "ok"      : le SKU du client est correct (dans son catalogue)
      - status "corrige" : SKU faux/absent remplacé via la désignation
      - status "inconnu" : ni le SKU ni la désignation ne matchent le catalogue
    """

    designation: Optional[str] = None   # nom produit tel qu'écrit sur la commande
    sku: Optional[str] = None           # SKU tel qu'envoyé par le client (peut être faux/None)
    quantity: Optional[float] = None
    # Résolution (rempli par resolver.py) :
    resolved_sku: Optional[str] = None  # SKU correct issu du catalogue du client
    sku_status: Optional[str] = None    # "ok" | "corrige" | "inconnu"


@dataclass
class OrderExtraction:
    """Données extraites du document par Claude (avant résolution master data).

    Seuls les champs de source « Commande » sont peuplés à l'extraction. Le code
    Customer (Clé 1) et les SKU corrigés sont ajoutés ensuite par resolver.py.
    """

    customer_name: Optional[str] = None
    partner_reference: Optional[str] = None
    requested_delivery_date: Optional[str] = None
    products: list[ProductLine] = field(default_factory=list)

    # Diagnostic (renvoyé par Claude, non destiné à l'ERP)
    comments: Optional[str] = None
    confidence: float = 0.0
    is_readable: bool = True
    quality_note: Optional[str] = None


@dataclass
class Resolution:
    """Résultat de la résolution master data pour une commande.

    `customer_code` (Clé 1) est None si le client n'a pas pu être retrouvé. La
    validation/correction des SKU est portée par chaque ProductLine
    (resolved_sku / sku_status). `status` alimente la colonne « Statut » Excel.
    """

    customer_code: Optional[str] = None   # Clé 1 (7 chiffres) ou None
    customer_name_master: Optional[str] = None  # nom canonique du client retrouvé
    matched: bool = False
    status: str = ""


# --- Validation 1 : format commande (avant résolution) -------------------
# Champs de source « Commande » obligatoires. Un seul manquant ⇒ rejet (422).
_REQUIRED_ORDER_FIELDS: list[tuple[str, str]] = [
    ("customer_name", "nom du client"),
    ("partner_reference", "référence partenaire"),
    ("requested_delivery_date", "date de livraison souhaitée"),
]


def _is_blank(value) -> bool:
    """True si la valeur est None ou une chaîne vide / espaces uniquement."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def validate_order(order: OrderExtraction) -> list[str]:
    """Validation de FORMAT (avant résolution). Vide ⇒ commande bien formée.

    Règles :
      - is_readable == False ⇒ rejet
      - un champ commande obligatoire manquant ⇒ rejet
      - aucune ligne produit, OU une quantité non numérique / <= 0 ⇒ rejet

    Le SKU n'est PAS contrôlé ici : il peut être faux ou absent (le client en
    envoie souvent de mauvais) — il est validé/corrigé à la résolution via le
    catalogue. La correspondance client/produit est vérifiée par
    `validate_resolution` APRÈS la résolution.
    """
    reasons: list[str] = []

    if order.is_readable is False:
        reasons.append("document illisible")

    missing = [label for attr, label in _REQUIRED_ORDER_FIELDS if _is_blank(getattr(order, attr, None))]
    if missing:
        reasons.append("champs manquants: " + ", ".join(missing))

    if not order.products:
        reasons.append("aucune ligne produit")
    else:
        bad_qty = False
        for p in order.products:
            qty = p.quantity
            if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
                bad_qty = True
        if bad_qty:
            reasons.append("quantité invalide (> 0 requis)")

    return reasons


def validate_resolution(order: OrderExtraction, resolution: Resolution) -> list[str]:
    """Validation APRÈS résolution (règle « A-revoir » stricte). Vide ⇒ valide.

    Rejet (422 → revue manuelle) si :
      - le client n'a pas été retrouvé dans la master data (pas de Clé 1) ;
      - au moins une ligne produit est hors du catalogue du client (status
        "inconnu" ou resolved_sku non conforme).
    """
    reasons: list[str] = []

    if not resolution.matched or _is_blank(resolution.customer_code):
        reasons.append(
            f"client introuvable dans la master data : {order.customer_name or '(nom absent)'}"
        )

    unknown = []
    for p in order.products:
        ok_sku = isinstance(p.resolved_sku, str) and _SKU_RE.match(p.resolved_sku or "")
        if p.sku_status == "inconnu" or not ok_sku:
            unknown.append(p.designation or p.sku or "(produit sans nom)")
    if unknown:
        reasons.append("produit(s) hors catalogue: " + ", ".join(unknown))

    return reasons


def build_record(
    order: OrderExtraction, resolution: Resolution, file_name: str
) -> dict:
    """Construit le record JSON renvoyé par /api/extract et consommé par /api/build.

    Le `sku` émis est le SKU RÉSOLU (correct). On conserve aussi le SKU d'origine
    et le statut de résolution pour l'affichage/diagnostic.
    """
    return {
        "customer_name": order.customer_name,
        "partner_reference": order.partner_reference,
        "requested_delivery_date": order.requested_delivery_date,
        "customer_code": resolution.customer_code,  # Clé 1
        "products": [
            {
                "designation": p.designation,
                "sku": p.resolved_sku,        # SKU correct (déliverable ERP)
                "input_sku": p.sku,           # ce que le client avait envoyé
                "sku_status": p.sku_status,   # ok | corrige | inconnu
                "quantity": p.quantity,
            }
            for p in order.products
        ],
        "resolution": {
            "customer_code": resolution.customer_code,
            "customer_name_master": resolution.customer_name_master,
            "matched": resolution.matched,
            "status": resolution.status,
        },
        "filename": file_name,
        "confidence": round(order.confidence, 2),
        "quality_note": order.quality_note,
    }

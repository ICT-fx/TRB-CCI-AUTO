"""Contrat de données partagé par tout le pipeline.

`OrderExtraction` est l'objet pivot : produit par anthropic_client, enrichi par
enrichment, écrit par excel_writer. Changer un champ ici impose de toucher le
schéma (schema.py) et l'écriture Excel (excel_writer.py) — commencer par ce
fichier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Un SKU valide est un code numérique à exactement 4 chiffres.
_SKU_RE = re.compile(r"^\d{4}$")


@dataclass
class ProductLine:
    """Une ligne produit (SKU) du document. La valeur peut être 0 (cas valide)."""

    sku: Optional[str] = None
    quantity: Optional[float] = None
    value: Optional[float] = None


@dataclass
class OrderExtraction:
    """Données extraites du document par Claude (avant enrichissement master data).

    Seuls les champs de source « Commande » sont peuplés ici. Les champs de
    source « Master Data » (TVA, monnaie, incoterm…) sont ajoutés ensuite par
    enrichment.py et portés par `MasterDataFields`.
    """

    # Source = Commande
    customer_name: Optional[str] = None          # #3 — clé de jointure master data
    partner_reference: Optional[str] = None       # #4 — n° commande fournisseur
    requested_delivery_date: Optional[str] = None  # #9
    incoterm_location: Optional[str] = None        # #15
    destination: Optional[str] = None              # #17
    products: list[ProductLine] = field(default_factory=list)  # #20-22

    # Diagnostic (renvoyé par Claude, non destiné à l'ERP)
    comments: Optional[str] = None
    confidence: float = 0.0
    is_readable: bool = True
    quality_note: Optional[str] = None


@dataclass
class MasterDataFields:
    """Champs de source « Master Data », résolus par jointure sur le client.

    Tous None si le client est introuvable. `status` décrit le résultat de la
    jointure (trouvé / introuvable) et alimente la colonne « Statut » de l'Excel.
    """

    numero_tva: Optional[str] = None              # #5
    monnaie: Optional[str] = None                 # #6
    conditions_paiement_jours: Optional[float] = None  # #7
    assurance: Optional[str] = None               # #8
    mode_expedition: Optional[str] = None         # #13
    incoterm: Optional[str] = None                # #14
    lieu_provenance: Optional[str] = None         # #16
    destination_edi: Optional[str] = None         # #18

    matched: bool = False
    status: str = ""


# --- Validation (règle « A-revoir » stricte) -----------------------------
# Champs de source « Commande » obligatoires. Un seul manquant ⇒ rejet (422).
# La résolution master data (client trouvé ou non) ne participe PAS à cette
# validation : un client hors master data est conservé, pas rejeté.
_REQUIRED_ORDER_FIELDS: list[tuple[str, str]] = [
    ("customer_name", "nom du client"),
    ("partner_reference", "référence partenaire"),
    ("requested_delivery_date", "date de livraison souhaitée"),
    ("destination", "destination"),
    # NB : "incoterm_location" (lieu de l'incoterm) est volontairement OPTIONNEL :
    # les commandes réelles ne le portent pas. Le re-rendre obligatoire rejetterait
    # toutes les commandes.
]


def _is_blank(value) -> bool:
    """True si la valeur est None ou une chaîne vide / espaces uniquement."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def validate_order(order: OrderExtraction) -> list[str]:
    """Renvoie la liste des raisons de rejet (vide ⇒ commande valide).

    Règles (spec) :
      - is_readable == False
      - un des champs commande obligatoires vide / None / blanc
      - aucun produit, OU un produit avec sku non conforme à ^\\d{4}$,
        quantity non numérique ou <= 0, value non numérique ou < 0
        (null/None interdit ; 0 autorisé pour value).

    NB : le master data (client introuvable) n'intervient pas ici.
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
        bad_sku = False
        bad_qty = False
        bad_val = False
        for p in order.products:
            sku = p.sku
            if not (isinstance(sku, str) and _SKU_RE.match(sku)):
                bad_sku = True
            qty = p.quantity
            if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
                bad_qty = True
            val = p.value
            if isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0:
                bad_val = True
        if bad_sku:
            reasons.append("SKU non conforme (4 chiffres requis)")
        if bad_qty:
            reasons.append("quantité invalide (> 0 requis)")
        if bad_val:
            reasons.append("valeur invalide (>= 0 requise)")

    return reasons


def build_record(
    order: OrderExtraction, master: MasterDataFields, file_name: str
) -> dict:
    """Construit le record JSON renvoyé par /api/extract et consommé par /api/build.

    Forme exacte (contrat Logic App) : champs commande, products[], master{},
    filename, confidence, quality_note.
    """
    return {
        "customer_name": order.customer_name,
        "partner_reference": order.partner_reference,
        "requested_delivery_date": order.requested_delivery_date,
        "incoterm_location": order.incoterm_location,
        "destination": order.destination,
        "products": [
            {"sku": p.sku, "quantity": p.quantity, "value": p.value}
            for p in order.products
        ],
        "master": {
            "numero_tva": master.numero_tva,
            "monnaie": master.monnaie,
            "conditions_paiement_jours": master.conditions_paiement_jours,
            "assurance": master.assurance,
            "mode_expedition": master.mode_expedition,
            "incoterm": master.incoterm,
            "lieu_provenance": master.lieu_provenance,
            "destination_edi": master.destination_edi,
            "matched": master.matched,
            "status": master.status,
        },
        "filename": file_name,
        "confidence": round(order.confidence, 2),
        "quality_note": order.quality_note,
    }

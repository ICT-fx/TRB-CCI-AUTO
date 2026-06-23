"""Contrat de données partagé par tout le pipeline.

`OrderExtraction` est l'objet pivot : produit par anthropic_client, enrichi par
enrichment, écrit par excel_writer. Changer un champ ici impose de toucher le
schéma (schema.py) et l'écriture Excel (excel_writer.py) — commencer par ce
fichier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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

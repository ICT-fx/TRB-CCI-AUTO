"""Enrichissement via master data : champs absents du document, résolus par jointure.

Pour l'instant la jointure se fait sur le NOM DU CLIENT (feuille `partenaires`).
Certaines données dépendront plus tard du produit ou d'autres critères ; ce
module est le point unique où ajouter de nouvelles tables / clés de jointure
sans toucher au reste du code (voir la note `extensibilité` en bas).

Source de données : `master_data.xlsx` livré à côté de ce module. Remplaçable
plus tard par SharePoint / l'ERP en ne changeant QUE ce fichier.
"""

from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

from openpyxl import load_workbook

from .models import MasterDataFields, OrderExtraction

logger = logging.getLogger(__name__)

MASTER_DATA_PATH = Path(__file__).with_name("master_data.xlsx")
PARTNERS_SHEET = "partenaires"

# Colonnes attendues dans la feuille `partenaires`. La 1re (nom_client) est la
# clé de jointure ; les autres alimentent MasterDataFields.
_PARTNER_KEY_COLUMN = "nom_client"
_PARTNER_FIELD_COLUMNS = [
    "numero_tva",
    "monnaie",
    "conditions_paiement_jours",
    "assurance",
    "mode_expedition",
    "incoterm",
    "lieu_provenance",
    "destination_edi",
]


def _normalize_key(name: str | None) -> str:
    """Normalise un nom pour la jointure : sans accents, minuscules, espaces réduits."""
    if not name:
        return ""
    # Décompose puis retire les diacritiques (é -> e), pour tolérer les variantes.
    decomposed = unicodedata.normalize("NFKD", str(name))
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(no_accents.lower().split())


class MasterDataStore:
    """Charge le master data une fois et résout les jointures.

    Conçu comme façade extensible : `enrich()` est le seul appelant ; ajouter
    une table (ex. par produit) = charger une 2e feuille ici + une méthode de
    lookup, sans changer function_app.py ni excel_writer.py.
    """

    def __init__(self, path: Path = MASTER_DATA_PATH) -> None:
        self._path = path
        self._partners: dict[str, dict[str, object]] = {}
        self._loaded = False
        self._available = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            logger.warning("master_data.xlsx introuvable (%s) — enrichissement désactivé.", self._path)
            return
        try:
            self._partners = self._load_partners()
            self._available = True
            logger.info("Master data chargé : %d partenaire(s).", len(self._partners))
        except Exception:  # pragma: no cover - robustesse au chargement
            logger.exception("Échec du chargement du master data — enrichissement désactivé.")

    def _load_partners(self) -> dict[str, dict[str, object]]:
        wb = load_workbook(self._path, data_only=True, read_only=True)
        try:
            if PARTNERS_SHEET not in wb.sheetnames:
                raise ValueError(f"Feuille '{PARTNERS_SHEET}' absente du master data.")
            ws = wb[PARTNERS_SHEET]
            rows = ws.iter_rows(values_only=True)
            header = next(rows, None)
            if not header:
                return {}
            index = {str(h).strip(): i for i, h in enumerate(header) if h is not None}
            if _PARTNER_KEY_COLUMN not in index:
                raise ValueError(f"Colonne clé '{_PARTNER_KEY_COLUMN}' absente du master data.")

            partners: dict[str, dict[str, object]] = {}
            for row in rows:
                if row is None:
                    continue
                raw_name = row[index[_PARTNER_KEY_COLUMN]]
                key = _normalize_key(raw_name)
                if not key:
                    continue
                record = {
                    col: (row[index[col]] if col in index and index[col] < len(row) else None)
                    for col in _PARTNER_FIELD_COLUMNS
                }
                partners[key] = record
            return partners
        finally:
            wb.close()

    def enrich(self, order: OrderExtraction) -> MasterDataFields:
        """Résout les champs master data pour une commande (jointure sur le client)."""
        self._ensure_loaded()

        if not self._available:
            return MasterDataFields(status="master data indisponible")

        key = _normalize_key(order.customer_name)
        record = self._partners.get(key)
        if record is None:
            logger.warning("Client introuvable dans le master data : %r", order.customer_name)
            return MasterDataFields(
                matched=False,
                status=f"client introuvable dans le master data : {order.customer_name or '(nom absent)'}",
            )

        logger.info("Client trouvé dans le master data : %r", order.customer_name)
        return MasterDataFields(
            numero_tva=_as_str(record.get("numero_tva")),
            monnaie=_as_str(record.get("monnaie")),
            conditions_paiement_jours=_as_number(record.get("conditions_paiement_jours")),
            assurance=_as_str(record.get("assurance")),
            mode_expedition=_as_str(record.get("mode_expedition")),
            incoterm=_as_str(record.get("incoterm")),
            lieu_provenance=_as_str(record.get("lieu_provenance")),
            destination_edi=_as_str(record.get("destination_edi")),
            matched=True,
            status="OK",
        )


def _as_str(value) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _as_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # Tolère "30 jours", "30j", etc. dans le master data.
    if isinstance(value, str):
        digits = "".join(c for c in value if c.isdigit())
        return float(digits) if digits else None
    return None


# Instance unique réutilisée entre invocations (worker chaud).
_store: MasterDataStore | None = None


def enrich(order: OrderExtraction) -> MasterDataFields:
    """Point d'entrée public : enrichit une commande depuis le master data."""
    global _store
    if _store is None:
        _store = MasterDataStore()
    return _store.enrich(order)


# ---------------------------------------------------------------------------
# Extensibilité (à venir, second temps) :
#   - Pour une donnée dépendant du PRODUIT : ajouter une feuille `produits`
#     dans master_data.xlsx, la charger dans _ensure_loaded, et faire le lookup
#     par SKU dans enrich() (par ligne produit).
#   - Pour d'autres critères : même schéma — une table + une méthode de lookup.
#   Le reste du pipeline (function_app, excel_writer) n'a pas à changer tant que
#   MasterDataFields reste le contrat de sortie.
# ---------------------------------------------------------------------------

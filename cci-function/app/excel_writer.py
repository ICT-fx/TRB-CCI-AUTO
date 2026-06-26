"""Génération de l'Excel CCI avec openpyxl — format forcé, déterministe.

Une ligne par commande : tous les champs d'en-tête une fois, puis les produits
étalés en colonnes (SKU 1 / Quantité 1 / Valeur 1, SKU 2 / …), puis des colonnes
de diagnostic. L'ordre des colonnes suit la spec Donnees_CCI.xlsx (#1 → #22).

Claude n'écrit jamais ce fichier : le code impose mécaniquement les colonnes.
"""

from __future__ import annotations

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from . import config
from .models import MasterDataFields, OrderExtraction

SHEET_NAME = "CCI"
_HEADER_FILL = "FF15578F"  # bleu TRB
_HEADER_FONT = "FFFFFFFF"
_MASTER_EMPTY_FILL = "FFFFFF00"  # jaune : cellule master data à compléter

# Détecte une chaîne susceptible d'être interprétée comme formule par Excel.
_FORMULA_PREFIX = re.compile(r"^[=+\-@\t\r]")


def _safe_cell(value):
    """Neutralise l'injection de formules.

    Les valeurs viennent de documents clients arbitraires : une cellule commençant
    par = + - @ tab ou CR pourrait être évaluée comme formule à l'ouverture. On
    préfixe ces chaînes d'une apostrophe. Les nombres ne sont jamais altérés
    (Excel ne les évalue pas).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return ""
    text = str(value)
    if _FORMULA_PREFIX.match(text):
        return "'" + text
    return text


# Colonnes d'en-tête (une valeur par commande), dans l'ordre de la spec.
# (libellé, fonction extrayant la valeur depuis (order, md))
_HEADER_COLUMNS: list[tuple[str, object]] = [
    ("Type de document", lambda o, m: config.DOCUMENT_TYPE),
    ("Description gabarit", lambda o, m: config.DOCUMENT_TEMPLATE_DESCRIPTION),
    ("Nom du client", lambda o, m: o.customer_name),
    ("Référence partenaire", lambda o, m: o.partner_reference),
    ("Numéro de TVA", lambda o, m: m.numero_tva),
    ("Monnaie comptable", lambda o, m: m.monnaie),
    ("Conditions de paiement (jours)", lambda o, m: m.conditions_paiement_jours),
    ("Assurance", lambda o, m: m.assurance),
    ("Date de livraison souhaitée", lambda o, m: o.requested_delivery_date),
    ("Délai de disponibilité", lambda o, m: None),   # à déterminer
    ("Délai d'expédition", lambda o, m: None),        # à déterminer
    ("Délai de livraison", lambda o, m: None),        # à déterminer
    ("Mode d'expédition", lambda o, m: m.mode_expedition),
    ("Incoterm", lambda o, m: m.incoterm),
    ("Lieu de l'incoterm", lambda o, m: o.incoterm_location),
    ("Lieu de provenance", lambda o, m: m.lieu_provenance),
    ("Destination", lambda o, m: o.destination),
    ("Destination EDI", lambda o, m: m.destination_edi),
    ("Stock logique", lambda o, m: None),             # à déterminer
]

# Colonnes de diagnostic (en fin de ligne).
_DIAGNOSTIC_COLUMNS = ["Nom du fichier", "Confiance", "Statut", "Note qualité"]


# --- Variante consolidée (multi-ligne, depuis des records dict) -----------
# Les 19 colonnes d'en-tête fixes, dans l'ordre, avec la fonction qui en extrait
# la valeur depuis un record (dict). Les colonnes master data lisent record["master"].
_FIXED_HEADER_COLUMNS: list[tuple[str, object]] = [
    ("Type de document", lambda r: config.DOCUMENT_TYPE),
    ("Description gabarit", lambda r: config.DOCUMENT_TEMPLATE_DESCRIPTION),
    ("Nom du client", lambda r: r.get("customer_name")),
    ("Référence partenaire", lambda r: r.get("partner_reference")),
    ("Numéro de TVA", lambda r: _master(r).get("numero_tva")),
    ("Monnaie comptable", lambda r: _master(r).get("monnaie")),
    ("Conditions de paiement (jours)", lambda r: _master(r).get("conditions_paiement_jours")),
    ("Assurance", lambda r: _master(r).get("assurance")),
    ("Date de livraison souhaitée", lambda r: r.get("requested_delivery_date")),
    ("Délai de disponibilité", lambda r: None),   # à déterminer
    ("Délai d'expédition", lambda r: None),        # à déterminer
    ("Délai de livraison", lambda r: None),        # à déterminer
    ("Mode d'expédition", lambda r: _master(r).get("mode_expedition")),
    ("Incoterm", lambda r: _master(r).get("incoterm")),
    ("Lieu de l'incoterm", lambda r: r.get("incoterm_location")),
    ("Lieu de provenance", lambda r: _master(r).get("lieu_provenance")),
    ("Destination", lambda r: r.get("destination")),
    ("Destination EDI", lambda r: _master(r).get("destination_edi")),
    ("Stock logique", lambda r: None),             # à déterminer
]

# Libellés des 8 colonnes master data : leurs cellules vides sont surlignées jaune.
_MASTER_HIGHLIGHT_LABELS = {
    "Numéro de TVA",
    "Monnaie comptable",
    "Conditions de paiement (jours)",
    "Assurance",
    "Mode d'expédition",
    "Incoterm",
    "Lieu de provenance",
    "Destination EDI",
}


def _master(record: dict) -> dict:
    m = record.get("master")
    return m if isinstance(m, dict) else {}


def _is_empty(value) -> bool:
    """True si une cellule master est « vide » (None ou chaîne blanche)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def build_consolidated_workbook(rows: list[dict]) -> bytes:
    """Construit l'Excel CCI consolidé : 1 feuille, 1 ligne par record.

    Colonnes : 19 en-têtes fixes, puis `SKU i / Quantité i / Valeur i` pour
    i = 1..MAX (MAX = nb max de produits dans le lot, au moins 1), puis les
    colonnes de diagnostic. Les cellules master data vides sont surlignées jaune.

    `rows` vide ⇒ classeur valide avec uniquement les en-têtes.
    """
    rows = rows or []

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    max_products = max((len(r.get("products") or []) for r in rows), default=0)
    max_products = max(max_products, 1)  # toujours au moins 1 groupe produit

    # 1) En-têtes.
    headers: list[str] = [label for label, _ in _FIXED_HEADER_COLUMNS]
    for i in range(1, max_products + 1):
        headers += [f"SKU {i}", f"Quantité {i}", f"Valeur {i}"]
    headers += _DIAGNOSTIC_COLUMNS
    ws.append(headers)

    # Index (1-based) des colonnes master à surligner si vides.
    highlight_cols = {
        idx
        for idx, (label, _) in enumerate(_FIXED_HEADER_COLUMNS, start=1)
        if label in _MASTER_HIGHLIGHT_LABELS
    }
    yellow_fill = PatternFill("solid", fgColor=_MASTER_EMPTY_FILL)

    # 2) Lignes de données.
    for record in rows:
        master = _master(record)
        values: list = [getter(record) for _, getter in _FIXED_HEADER_COLUMNS]
        products = record.get("products") or []
        for i in range(max_products):
            if i < len(products):
                p = products[i] or {}
                values += [p.get("sku"), p.get("quantity"), p.get("value")]
            else:
                values += [None, None, None]
        values += [
            record.get("filename"),
            record.get("confidence"),
            master.get("status") or "OK",
            record.get("quality_note"),
        ]

        ws.append([_safe_cell(v) for v in values])

        # Surlignage jaune des cellules master data vides (par cellule, par ligne).
        row_idx = ws.max_row
        for col_idx in highlight_cols:
            raw_value = values[col_idx - 1]
            if _is_empty(raw_value):
                ws.cell(row=row_idx, column=col_idx).fill = yellow_fill

    # 3) Style + figeage de l'en-tête.
    header_font = Font(bold=True, color=_HEADER_FONT)
    header_fill = PatternFill("solid", fgColor=_HEADER_FILL)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"

    # Largeurs de colonnes lisibles (bornées).
    for idx in range(1, len(headers) + 1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = min(max(len(headers[idx - 1]) + 2, 12), 44)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_workbook(
    order: OrderExtraction, master: MasterDataFields, file_name: str
) -> bytes:
    """Construit le classeur .xlsx (1 ligne) et renvoie ses octets."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    # 1) En-têtes : champs d'en-tête + N groupes produit + diagnostic.
    headers: list[str] = [label for label, _ in _HEADER_COLUMNS]
    for i in range(1, len(order.products) + 1):
        headers += [f"SKU {i}", f"Quantité {i}", f"Valeur {i}"]
    headers += _DIAGNOSTIC_COLUMNS
    ws.append(headers)

    # 2) Ligne de données.
    row: list = [getter(order, master) for _, getter in _HEADER_COLUMNS]
    for product in order.products:
        row += [product.sku, product.quantity, product.value]
    row += [
        file_name,
        round(order.confidence, 2),
        master.status or ("OK" if order.is_readable else "document peu lisible"),
        order.quality_note,
    ]
    ws.append([_safe_cell(v) for v in row])

    # 3) Style + figeage de l'en-tête.
    header_font = Font(bold=True, color=_HEADER_FONT)
    header_fill = PatternFill("solid", fgColor=_HEADER_FILL)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"

    # Largeurs de colonnes lisibles (bornées).
    for idx, _ in enumerate(headers, start=1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = min(max(len(headers[idx - 1]) + 2, 12), 44)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

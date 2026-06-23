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

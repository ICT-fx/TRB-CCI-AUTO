"""Génération de l'Excel CCI avec openpyxl — format forcé, déterministe.

Format LONG : **une ligne par article**. Les colonnes sont fixes —
`Nom du client | Clé 1 | Référence partenaire | Date de livraison souhaitée |
SKU | Quantité | Nom du fichier`. Les champs d'en-tête (dont la **Clé 1** et la
**Référence partenaire**) sont **répétés à l'identique** sur chaque ligne d'une
même commande : c'est ce couple qui permet de regrouper les articles d'une même
commande. Une commande de N articles = N lignes.

Le SKU écrit est le SKU RÉSOLU (correct, issu du catalogue du client). Seuls les
SKU AMBIGUS (l'IA a hésité entre plusieurs produits proches) sont surlignés
jaune = à vérifier ; les corrections évidentes ne le sont pas. Une Clé 1 vide ou
une date imprécise (« A-revoir manuellement ») sont aussi surlignées jaune. Il
n'y a pas de colonne de statut : le jaune est le seul signal. Claude n'écrit
jamais ce fichier : le code impose mécaniquement les colonnes.
"""

from __future__ import annotations

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .models import (
    DELIVERY_DATE_REVIEW,
    OrderExtraction,
    Resolution,
    suggested_filename,
)

SHEET_NAME = "CCI"
_HEADER_FILL = "FF15578F"  # bleu TRB
_HEADER_FONT = "FFFFFFFF"
_HIGHLIGHT_FILL = "FFFFFF00"  # jaune : à vérifier (SKU ambigu / Clé 1 vide)

# Détecte une chaîne susceptible d'être interprétée comme formule par Excel.
_FORMULA_PREFIX = re.compile(r"^[=+\-@\t\r]")

# Format long : 2 colonnes fixes SKU / Quantité (une ligne par article).
# Le statut n'est pas une colonne : un SKU ambigu est simplement surligné jaune.
_SKU_QTY_HEADERS = ["SKU", "Quantité"]

# Colonne de diagnostic (en fin de ligne) : le nom composé du fichier.
_DIAGNOSTIC_COLUMNS = ["Nom du fichier"]


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


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _append_order_rows(
    ws, fixed_values: list, products: list[tuple], filename, yellow,
    *, cle1_col: int | None, date_col: int | None, sku_col: int,
) -> None:
    """Ajoute UNE LIGNE PAR ARTICLE (format long) et répète les champs d'en-tête.

    `products` : liste de `(sku, quantity, ambiguous)`. Une commande sans article
    produit tout de même une ligne (SKU/Quantité vides) pour ne pas la perdre.
    Surlignage jaune : Clé 1 vide, date « A-revoir manuellement », SKU ambigu.
    """
    lines = products or [(None, None, False)]
    for sku, qty, ambiguous in lines:
        ws.append([_safe_cell(v) for v in (list(fixed_values) + [sku, qty, filename])])
        r = ws.max_row
        if cle1_col and _is_empty(fixed_values[cle1_col - 1]):
            ws.cell(row=r, column=cle1_col).fill = yellow
        if date_col and fixed_values[date_col - 1] == DELIVERY_DATE_REVIEW:
            ws.cell(row=r, column=date_col).fill = yellow
        if ambiguous:
            ws.cell(row=r, column=sku_col).fill = yellow


def _finish_sheet(ws, headers: list[str]) -> None:
    """Style d'en-tête + figeage + largeurs de colonnes."""
    header_font = Font(bold=True, color=_HEADER_FONT)
    header_fill = PatternFill("solid", fgColor=_HEADER_FILL)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    for idx in range(1, len(headers) + 1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = min(max(len(headers[idx - 1]) + 2, 12), 44)


# --- Colonnes d'en-tête fixes (champs extraits + Clé 1) -------------------
# Variante « order object » (build_workbook, 1 ligne) : getter(order, resolution).
_HEADER_COLUMNS: list[tuple[str, object]] = [
    ("Nom du client", lambda o, r: o.customer_name),
    ("Clé 1", lambda o, r: r.customer_code),  # code Customer résolu
    ("Référence partenaire", lambda o, r: o.partner_reference),
    ("Date de livraison souhaitée", lambda o, r: o.requested_delivery_date),
]

# Variante « record dict » (build_consolidated_workbook, N lignes) : getter(record).
_FIXED_HEADER_COLUMNS: list[tuple[str, object]] = [
    ("Nom du client", lambda r: r.get("customer_name")),
    ("Clé 1", lambda r: r.get("customer_code")),
    ("Référence partenaire", lambda r: r.get("partner_reference")),
    ("Date de livraison souhaitée", lambda r: r.get("requested_delivery_date")),
]

_CLE1_LABEL = "Clé 1"
_DATE_LABEL = "Date de livraison souhaitée"


def build_consolidated_workbook(rows: list[dict]) -> bytes:
    """Construit l'Excel CCI consolidé : 1 feuille, **1 ligne par article**.

    Colonnes fixes : en-têtes (dont Clé 1 + Référence partenaire), puis `SKU` /
    `Quantité`, puis « Nom du fichier ». Les articles d'une même commande partagent
    la même Clé 1 et la même référence (lignes répétées). Les SKU ambigus, une
    Clé 1 manquante et une date imprécise sont surlignés jaune.

    `rows` vide ⇒ classeur valide avec uniquement les en-têtes.
    """
    rows = rows or []

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    fixed = _FIXED_HEADER_COLUMNS
    headers: list[str] = [label for label, _ in fixed] + _SKU_QTY_HEADERS + _DIAGNOSTIC_COLUMNS
    ws.append(headers)

    cle1_col = next((i for i, (label, _) in enumerate(fixed, start=1) if label == _CLE1_LABEL), None)
    date_col = next((i for i, (label, _) in enumerate(fixed, start=1) if label == _DATE_LABEL), None)
    sku_col = len(fixed) + 1
    yellow = PatternFill("solid", fgColor=_HIGHLIGHT_FILL)

    for record in rows:
        fixed_values = [getter(record) for _, getter in fixed]
        products = [
            ((p or {}).get("sku"), (p or {}).get("quantity"), (p or {}).get("sku_status") == "ambigu")
            for p in (record.get("products") or [])
        ]
        filename = record.get("suggested_filename") or record.get("filename")
        _append_order_rows(
            ws, fixed_values, products, filename, yellow,
            cle1_col=cle1_col, date_col=date_col, sku_col=sku_col,
        )

    _finish_sheet(ws, headers)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_ERROR_SHEET = "A-revoir"
_ERROR_COLUMNS = ["Nom du fichier", "Date de l'erreur", "Observation"]


def build_error_report(rows: list[dict]) -> bytes:
    """Excel de reporting des commandes rejetées (dossier A-revoir).

    1 ligne par commande en erreur. Chaque `row` (dict) :
      - nom_fichier : le nouveau nom (contenant le nom du client)
      - date        : date de l'erreur (déjà formatée, ex. 02/07/2026)
      - raison      : motif du rejet ; note : note qualité (optionnelle)
    Colonnes : Nom du fichier | Date de l'erreur | Observation.
    `rows` vide ⇒ classeur valide avec uniquement les en-têtes.
    """
    rows = rows or []
    wb = Workbook()
    ws = wb.active
    ws.title = _ERROR_SHEET
    ws.append(_ERROR_COLUMNS)
    for r in rows:
        r = r if isinstance(r, dict) else {}
        raison = (r.get("raison") or "").strip()
        note = (r.get("note") or "").strip()
        observation = (raison + (" — " + note if note else "")).strip(" —")
        ws.append([
            _safe_cell(r.get("nom_fichier")),
            _safe_cell(r.get("date")),
            _safe_cell(observation),
        ])
    _finish_sheet(ws, _ERROR_COLUMNS)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_workbook(
    order: OrderExtraction, resolution: Resolution, file_name: str
) -> bytes:
    """Construit le classeur .xlsx (1 ligne par article) et renvoie ses octets."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    headers: list[str] = [label for label, _ in _HEADER_COLUMNS] + _SKU_QTY_HEADERS + _DIAGNOSTIC_COLUMNS
    ws.append(headers)

    fixed_values = [getter(order, resolution) for _, getter in _HEADER_COLUMNS]
    products = [(p.resolved_sku, p.quantity, p.sku_status == "ambigu") for p in order.products]
    filename = suggested_filename(order.customer_name, order.requested_delivery_date, file_name)
    cle1_col = next((i for i, (label, _) in enumerate(_HEADER_COLUMNS, start=1) if label == _CLE1_LABEL), None)
    date_col = next((i for i, (label, _) in enumerate(_HEADER_COLUMNS, start=1) if label == _DATE_LABEL), None)
    yellow = PatternFill("solid", fgColor=_HIGHLIGHT_FILL)
    _append_order_rows(
        ws, fixed_values, products, filename, yellow,
        cle1_col=cle1_col, date_col=date_col, sku_col=len(_HEADER_COLUMNS) + 1,
    )

    _finish_sheet(ws, headers)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

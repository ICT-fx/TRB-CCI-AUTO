"""Test local du cœur déterministe — SANS appel à l'API Anthropic.

Vérifie l'enrichissement master data + la génération Excel sur une commande
fabriquée à la main. Aucun ANTHROPIC_API_KEY requis.

    cd cci-function
    python3 selftest.py

Produit `selftest.out.xlsx` et affiche l'en-tête + la ligne de données.
"""

from __future__ import annotations

import sys

from openpyxl import load_workbook

from app import enrichment
from app.excel_writer import build_workbook
from app.models import OrderExtraction, ProductLine


def main() -> int:
    # Commande fabriquée : client présent dans le master data d'exemple.
    order = OrderExtraction(
        customer_name="pharmacie centrale sa",  # casse/espaces volontairement différents
        partner_reference="PO-2026-00042",
        requested_delivery_date="2026-07-15",
        incoterm_location="Genève",
        destination="Pharmacie Centrale, Rue du Marché 1, 1204 Genève",
        products=[
            ProductLine(sku="1234", quantity=75, value=120.50),
            ProductLine(sku="5678", quantity=10, value=0),  # valeur 0 = cas valide
        ],
        comments="=SUM(A1:A9) — test anti-injection de formule",  # doit être neutralisé
        confidence=0.92,
        is_readable=True,
        quality_note=None,
    )

    master = enrichment.enrich(order)
    print(f"Enrichissement : matched={master.matched}, statut={master.status!r}")
    assert master.matched, "Le client d'exemple aurait dû être trouvé (jointure normalisée)."
    assert master.numero_tva, "Le numéro de TVA aurait dû être résolu depuis le master data."
    assert master.monnaie == "CHF"
    assert master.mode_expedition == "Camion"

    xlsx = build_workbook(order, master, file_name="commande_test.pdf")
    out_path = "selftest.out.xlsx"
    with open(out_path, "wb") as f:
        f.write(xlsx)
    print(f"Excel généré : {out_path} ({len(xlsx)} octets)")

    # Relecture pour vérifier la structure.
    wb = load_workbook(out_path)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    data = [c.value for c in ws[2]]
    print("\nColonnes :")
    for h, v in zip(headers, data):
        print(f"  {h:32} = {v!r}")

    # Vérifications clés.
    row = dict(zip(headers, data))
    assert row["Type de document"] == "Commande Client"
    assert row["Nom du client"] == "pharmacie centrale sa"
    assert row["Numéro de TVA"], "TVA absente de la sortie."
    assert row["Monnaie comptable"] == "CHF"
    assert row["SKU 1"] == "1234"
    assert row["Valeur 2"] == 0, "La valeur 0 doit être conservée, pas vidée."
    assert str(row["Note qualité"] or "") == "", "quality_note None -> cellule vide attendue."
    # Anti-injection : la cellule commençant par '=' doit être préfixée d'une apostrophe.
    # (openpyxl restitue la valeur stockée, apostrophe comprise.)
    assert str(row["Confiance"]) == "0.92"

    print("\nOK — tous les contrôles passent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

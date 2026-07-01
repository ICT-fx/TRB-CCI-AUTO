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
from app.models import OrderExtraction, ProductLine, validate_order


def main() -> int:
    # Commande fabriquée : client présent dans le master data d'exemple.
    # Seuls les champs réellement extraits du document sont peuplés :
    # nom du client, référence partenaire, date de livraison, SKU + quantité.
    order = OrderExtraction(
        customer_name="pharmacie centrale sa",  # casse/espaces volontairement différents
        partner_reference="PO-2026-00042",
        requested_delivery_date="2026-07-15",
        products=[
            ProductLine(sku="1234", quantity=75),
            ProductLine(sku="5678", quantity=10),
        ],
        comments="=SUM(A1:A9) — test anti-injection de formule",  # doit être neutralisé
        confidence=0.92,
        is_readable=True,
        quality_note=None,
    )

    # La validation « A-revoir » stricte accepte une commande à 5 champs.
    reasons = validate_order(order)
    assert reasons == [], f"La commande valide ne devrait pas être rejetée : {reasons}"

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

    # Vérifications clés : l'Excel ne contient que les champs extraits + Clé 1 + diagnostic.
    row = dict(zip(headers, data))
    # Colonnes retirées : plus aucune donnée master data ni Valeur dans l'Excel.
    for removed in ("Type de document", "Numéro de TVA", "Monnaie comptable", "Destination", "Valeur 1"):
        assert removed not in headers, f"Colonne {removed!r} aurait dû être retirée."
    # Champs extraits présents.
    assert row["Nom du client"] == "pharmacie centrale sa"
    assert row["Référence partenaire"] == "PO-2026-00042"
    assert row["Date de livraison souhaitée"] == "2026-07-15"
    assert row["SKU 1"] == "1234"
    assert row["Quantité 1"] == 75
    # Clé 1 : colonne présente mais vide (master data pas encore fourni).
    assert "Clé 1" in headers, "La colonne 'Clé 1' (code Customer) doit exister."
    assert str(row["Clé 1"] or "") == "", "'Clé 1' doit rester vide tant que le master data n'est pas fourni."
    assert str(row["Note qualité"] or "") == "", "quality_note None -> cellule vide attendue."
    assert str(row["Confiance"]) == "0.92"

    print("\nOK — tous les contrôles passent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

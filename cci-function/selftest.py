"""Test local du cœur déterministe — SANS appel à l'API Anthropic.

L'appel Claude de résolution est remplacé par une réponse simulée (monkeypatch),
si bien que le mapping résolution + le garde-fou master data + la génération Excel
sont testés de bout en bout contre la VRAIE master data (app/master_data.xlsx),
sans ANTHROPIC_API_KEY.

    cd cci-function
    python3 selftest.py

Produit `selftest.out.xlsx` et affiche l'en-tête + la ligne de données.
"""

from __future__ import annotations

import sys

from openpyxl import load_workbook

from app import anthropic_client, resolver
from app.excel_writer import build_workbook
from app.models import (
    OrderExtraction,
    ProductLine,
    validate_order,
    validate_resolution,
)


def _fake_resolution(customer_code, lines):
    """Fabrique une fonction qui imite anthropic_client.resolve_order."""
    def _call(order, master_context):
        return {
            "customer_code": customer_code,
            "customer_status": "ok" if customer_code else "introuvable",
            "lines": lines,
        }
    return _call


def main() -> int:
    # Commande fabriquée pour un client réel du master data (Dea Lens Project,
    # Clé 1 = 2780008). Le nom diffère un peu et le 1er SKU est FAUX -> doit être
    # corrigé en 1311 via la désignation ; le 2e est correct (1136).
    # customer_name commence par '=' pour tester l'anti-injection de formule.
    order = OrderExtraction(
        customer_name="=Dea Lens Project",
        partner_reference="PO-2026-00042",
        requested_delivery_date="2026-07-15",
        products=[
            ProductLine(designation="Vismed Multi 10", sku="9999", quantity=100),
            ProductLine(designation="Vismed 20", sku="1136", quantity=50),
        ],
        comments="commande de test",
        confidence=0.92,
        is_readable=True,
        quality_note=None,
    )

    # Validation de format : doit passer (le SKU faux n'est pas gaté ici).
    assert validate_order(order) == [], "La validation de format ne devrait pas rejeter."

    # Résolution simulée (pas d'appel réseau).
    anthropic_client.resolve_order = _fake_resolution(
        "2780008",
        [
            {"designation": "Vismed Multi 10", "input_sku": "9999", "resolved_sku": "1311", "status": "corrige"},
            {"designation": "Vismed 20", "input_sku": "1136", "resolved_sku": "1136", "status": "ok"},
        ],
    )
    resolution = resolver.resolve(order)
    print(f"Résolution : code={resolution.customer_code!r}, matched={resolution.matched}, statut={resolution.status!r}")

    assert resolution.matched, "Le client d'exemple aurait dû être retrouvé."
    assert resolution.customer_code == "2780008"
    assert resolution.customer_name_master == "Dea Lens Project d.o.o."
    assert order.products[0].resolved_sku == "1311" and order.products[0].sku_status == "corrige", "SKU faux -> corrigé en 1311"
    assert order.products[1].resolved_sku == "1136" and order.products[1].sku_status == "ok", "SKU correct -> ok"
    assert validate_resolution(order, resolution) == [], "Commande valide, ne devrait pas être rejetée."

    xlsx = build_workbook(order, resolution, file_name="commande_test.pdf")
    out_path = "selftest.out.xlsx"
    with open(out_path, "wb") as f:
        f.write(xlsx)
    print(f"Excel généré : {out_path} ({len(xlsx)} octets)")

    wb = load_workbook(out_path)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    data = [c.value for c in ws[2]]
    print("\nColonnes :")
    for h, v in zip(headers, data):
        print(f"  {h:20} = {v!r}")

    row = dict(zip(headers, data))
    # Colonnes retirées de l'ancien format : plus de master data ni Valeur.
    for removed in ("Numéro de TVA", "Monnaie comptable", "Destination", "Valeur 1"):
        assert removed not in headers, f"Colonne {removed!r} aurait dû être absente."
    assert row["Clé 1"] == "2780008", "Clé 1 (code Customer) doit être remplie."
    assert row["Nom du client"] == "'=Dea Lens Project", "Nom avec '=' doit être neutralisé (apostrophe)."
    assert row["Référence partenaire"] == "PO-2026-00042"
    assert row["Date de livraison souhaitée"] == "2026-07-15"
    assert row["SKU 1"] == "1311", "SKU 1 doit être le SKU corrigé."
    assert row["Quantité 1"] == 100
    assert row["SKU 1 (statut)"] == "corrige"
    assert row["SKU 2"] == "1136"
    assert row["SKU 2 (statut)"] == "ok"
    assert str(row["Confiance"]) == "0.92"

    # --- Cas de rejet (A-revoir) : client introuvable ---------------------
    order2 = OrderExtraction(
        customer_name="Client Inexistant SARL",
        partner_reference="PO-X",
        requested_delivery_date="2026-08-01",
        products=[ProductLine(designation="Vismed Multi 10", sku="1311", quantity=10)],
        confidence=0.8, is_readable=True,
    )
    anthropic_client.resolve_order = _fake_resolution(
        None,
        [{"designation": "Vismed Multi 10", "input_sku": "1311", "resolved_sku": None, "status": "inconnu"}],
    )
    res2 = resolver.resolve(order2)
    reasons2 = validate_resolution(order2, res2)
    assert reasons2, "Un client introuvable doit être rejeté (A-revoir)."
    print(f"\nRejet attendu (client introuvable) : {reasons2}")

    # --- Cas de rejet : produit hors catalogue (garde-fou anti-hallucination) --
    order3 = OrderExtraction(
        customer_name="Dea Lens Project",
        partner_reference="PO-Y",
        requested_delivery_date="2026-08-02",
        products=[ProductLine(designation="Produit fantôme", sku="0000", quantity=5)],
        confidence=0.8, is_readable=True,
    )
    # Claude prétend un SKU 4242 qui n'est PAS au catalogue de 2780008 -> rejeté par le garde-fou.
    anthropic_client.resolve_order = _fake_resolution(
        "2780008",
        [{"designation": "Produit fantôme", "input_sku": "0000", "resolved_sku": "4242", "status": "ok"}],
    )
    res3 = resolver.resolve(order3)
    assert order3.products[0].sku_status == "inconnu", "Un SKU hors catalogue doit être forcé à 'inconnu'."
    reasons3 = validate_resolution(order3, res3)
    assert reasons3, "Un produit hors catalogue doit être rejeté (A-revoir)."
    print(f"Rejet attendu (produit hors catalogue) : {reasons3}")

    print("\nOK — tous les contrôles passent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

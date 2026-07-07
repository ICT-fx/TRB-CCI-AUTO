# Jeu de démo — commandes truquées + master data de substitution

Ce dossier contient un **jeu de test 100 % fictif** pour faire tourner une démo du
pipeline CCI **sans exposer de données réelles** (noms clients, tarifs).

- Les **25 commandes** de `../Commandesafalsifier/` ont été **retruquées** : noms de
  clients fictifs, **prix délirants**, **quantités entre 1 et 30**. Les **vrais noms de
  produits** TRB sont conservés, ainsi que les blocs/adresses TRB (non sensibles).
- Une **master data de substitution** cohérente est générée pour que ~20 commandes se
  résolvent et **5 partent en « À-revoir » (422)**.

> ⚠️ Les prix ne sont **pas** lus par l'outil (il extrait désignation + SKU + quantité).
> Les « prix délirants » servent donc à l'anonymisation / au réalisme visuel — ils
> n'ont aucun effet sur la résolution. Les quantités 1–30, elles, sont bien lues.

Design complet : [`../docs/superpowers/specs/2026-07-03-demo-fake-orders-design.md`](../docs/superpowers/specs/2026-07-03-demo-fake-orders-design.md).

---

## Contenu

| Chemin | Rôle |
|---|---|
| `faked_orders.json` | **Source de vérité** : les 25 commandes (client fictif, code, réf, dates, devise, lignes produit, `outcome`). |
| `make_orders.py` | (Re)génère `faked_orders.json`. |
| `render_orders.py` | Rend les 25 PDF dans `commandes_fake/` (HTML paramétré → PDF via Chrome headless). |
| `build_demo_master_data.py` | Vérifie les invariants puis écrit `../cci-function/app/master_data.xlsx`. |
| `commandes_fake/*.pdf` | Les 25 commandes truquées (à donner en entrée à `/api/extract`). |

La **vraie** master data est sauvegardée dans
`../cci-function/app/master_data.REEL.backup.xlsx` (intacte).

---

## Régénérer / rejouer

```bash
cd "TRB CCI AUTO"
source cci-function/.venv/bin/activate          # openpyxl + pymupdf

python3 demo/make_orders.py                      # → faked_orders.json
python3 demo/render_orders.py                    # → commandes_fake/*.pdf (Chrome requis)
python3 demo/build_demo_master_data.py           # vérifie invariants → master_data.xlsx (substitution)
python3 demo/build_demo_master_data.py --check    # vérifie seulement, sans écrire
```

## Restaurer la vraie master data

```bash
cp cci-function/app/master_data.REEL.backup.xlsx cci-function/app/master_data.xlsx
```

> Note : `cci-function/selftest.py` teste en dur un client **réel** (code `2780008`).
> Il n'est vert **qu'avec la vraie** master data — restaure le backup avant de le lancer.

---

## Pourquoi la démo est déterministe

Les PDF **et** la master data sont générés depuis la **même** source
(`faked_orders.json`). `build_demo_master_data.py` **asserte** avant d'écrire :

- commande `pass` ⇒ client présent **et** chaque `(code, sku, désignation)` au catalogue ;
- `fail_client` ⇒ client **absent** de la feuille `clients` (et nom clairement distinct) ;
- `fail_product` ⇒ la ligne **intrus** est **hors** du catalogue du client (les autres y sont).

Le pipeline réel passe par Claude (match flou du nom + correction SKU par désignation) ;
il n'est pas rejouable hors-ligne, mais cette cohérence stricte rend le résultat attendu.

---

## Résultat attendu par commande

- **20 passent** (record 200, Clé 1 + SKU renseignés)
- **5 en À-revoir (422)** : 3 « client introuvable » + 2 « produit hors catalogue »

| # | Fichier source | Commande truquée (`.pdf`) | Client fictif | Code | Skin | Produits (SKU) | Résultat attendu |
|---|---|---|---|---|---|---|---|
| 1 | AG.pdf | AG.pdf | Rheintal Pharmazeutika GmbH | 9000001 | sap | 1082 | ✅ passe (record 200) |
| 2 | Austria.pdf | Austria.pdf | Alpenmed Vertriebs GmbH | 9000002 | trb_orderform | 1780, 1781, 1013, 1082 | ✅ passe (record 200) |
| 3 | brazil.pdf | brazil.pdf | Farma Atlântico Indústria Ltda | 9000003 | trb_orderform | 1082, 0587 | ✅ passe (record 200) |
| 4 | brudylab.pdf | brudylab.pdf | Laboratorios Brisamar S.L.U. | 9000004 | invoice | 0687 | ✅ passe (record 200) |
| 5 | cigalah drug store.pdf | cigalah.pdf | Emirates Crescent Drug Store L.L.C. | 9000005 | grid | 1328, 1325 | ✅ passe (record 200) |
| 6 | Combiphar.pdf | Combiphar.pdf | PT Nusantara Farma Sentosa | 9000006 | sap | 1344 | ✅ passe (record 200) |
| 7 | Corporacion Am.pdf | Corporacion_Am.pdf | Distribuidora Centroamericana de Farmacia, S.A. | 9000007 | invoice | 1344 | ✅ passe (record 200) |
| 8 | Doc G.pdf | Doc_G.pdf | Farmaceutici Aurelia S.r.l. | 9000008 | sap | 1621, 1749 | ⛔ À-revoir — Client inconnu |
| 9 | Hong kong.pdf | Hong_kong.pdf | Jade Harbour Medical (Hong Kong) Ltd. | 9000009 | grid | 1719 | ✅ passe (record 200) |
| 10 | Kukje.pdf | Kukje.pdf | Hankuk Medi Pharm Co., Ltd. | 9000010 | letter | 1313 | ✅ passe (record 200) |
| 11 | Mephropharm.pdf | Mephropharm.pdf | PT Bumi Sehat Farmasi | 9000011 | sap | 1780, 1784 | ✅ passe (record 200) |
| 12 | Optimed.pdf | Optimed.pdf | Medikom Adria d.o.o. | 9000012 | trb_orderform | 0899, 0903, 0687, 1083, 1307, 1784 **⟵ intrus** | ⛔ À-revoir — Produit inhabituel |
| 13 | PL.pdf | PL.pdf | Vistula Pharma Sp. z o.o. | 9000013 | trb_orderform | 1082 | ✅ passe (record 200) |
| 14 | river pharma.pdf | river_pharma.pdf | Andes River Pharma S.A.C. | 9000014 | invoice | 1203 | ⛔ À-revoir — Client inconnu |
| 15 | Serpin.pdf | Serpin.pdf | Levant Serapis Dış Ticaret Ltd. Şti. | 9000015 | trb_orderform | 0687, 0899, 0903, 1083 | ⛔ À-revoir — Client inconnu |
| 16 | star int.pdf | star_int.pdf | Nile Star Medical Co. | 9000016 | grid | 0587, 1013, 1082, 1202 | ✅ passe (record 200) |
| 17 | synthemedic.pdf | synthemedic.pdf | Atlas Médic S.A. | 9000017 | dotmatrix | 1083 | ✅ passe (record 200) |
| 18 | TH.pdf | TH.pdf | Siam Vision Distribution Ltd. | 9000018 | trb_po | 1604 | ✅ passe (record 200) |
| 19 | UK.pdf | UK.pdf | Albion Pharma Distribution Ltd | 9000019 | grid | 1297, 1344 **⟵ intrus** | ⛔ À-revoir — Produit inhabituel |
| 20 | VT.pdf | VT.pdf | Mekong Health Distribution Co., Ltd. | 9000020 | trb_po | 1736, 1874, 1580, 1570 | ✅ passe (record 200) |
| 21 | Al tafaol.pdf | Al_tafaol.pdf | Al Wafra Trading Company W.L.L. | 9000021 | modern | 1013, 1203, 1325, 1328 | ✅ passe (record 200) |
| 22 | france.pdf | france.pdf | Léman Pharma Distribution SAS | 9000022 | trb_orderform | 1013 | ✅ passe (record 200) |
| 23 | malaysia.pdf | malaysia.pdf | Selatan Vision Sdn Bhd | 9000023 | modern | 0687, 0846, 1083, 0899, 1255, 1658, 1659 | ✅ passe (record 200) |
| 24 | dekhon.pdf | dekhon.pdf | Indus Crescent Pharma (Pvt) Ltd | 9000024 | invoice | 1083, 1255 | ✅ passe (record 200) |
| 25 | propharma.pdf | propharma.pdf | Gulf Meridian Medical Supplies L.L.C. | 9000025 | invoice | 0587, 1013, 1203 | ✅ passe (record 200) |

# Spec — CCI : Excel consolidé, nomenclature SKU, règle A-revoir stricte

Date : 2026-06-26
Statut : validé (à implémenter)

## Contexte

Le pipeline CCI (Azure Function + Logic App `trb-cci-logic`) fonctionne mais
3 problèmes sont à corriger :

1. **SKU mal détectés** : pas de format imposé → l'IA sort parfois des codes
   faux (ex. un code client `683XX` mis en SKU). Le SKU doit être un **code
   numérique à 4 chiffres**.
2. **Documents illisibles non rejetés** : un doc caviardé au feutre noir
   ressort un Excel avec des données fausses au lieu d'aller en `A-revoir`. La
   fonction ne renvoie 422 que si l'IA déclare `is_readable=false`.
3. **Un Excel par document** au lieu d'**un seul Excel par lot** (1 ligne =
   1 commande), ce qui est l'exigence forte.

## Décisions (validées)

| Sujet | Décision |
|---|---|
| SKU | Code **4 chiffres** (`^[0-9]{4}$`). Non conforme ⇒ commande rejetée (A-revoir). |
| A-revoir si manque | Nom client · Réf. partenaire · Date livraison · Lieu incoterm · Destination · ou aucun produit valide (SKU 4ch + Qté>0 + Valeur≥0). |
| Client hors master data | **Garder** la ligne ; cases master vides **surlignées jaune** + statut « client introuvable ». PAS A-revoir. |
| Sortie | **1 seul** `CCI-Lot-AAAAMMJJ-HHMMSS.xlsx`, **1 ligne/commande**, produits en colonnes. 0 commande valide ⇒ aucun fichier. |
| Archivage | PDF OK → `Commandes-Done` ; PDF rejeté → `A-revoir`. |

## Architecture

Séparer **extraction** et **génération Excel** dans l'Azure Function :

### `POST /api/extract`  (réponse modifiée : JSON au lieu de xlsx)
- Entrée : 1 fichier brut (corps) + `?filename=<nom>&code=<clé>` (inchangé).
- **200** : renvoie une **ligne JSON** (record) si la commande est valide.
- **422** : document à rejeter (illisible / champ obligatoire manquant / SKU non
  conforme). Corps JSON `{error, fichier, raison, confiance?, note_qualite?}`.
- 400/500/502 : inchangés (corps vide, type non supporté, erreur Claude…).

**Record JSON renvoyé (200)** — contrat exact consommé par le Logic App :
```json
{
  "customer_name": "RheinCare Solutions GmbH",
  "partner_reference": "PO 8362",
  "requested_delivery_date": "2027-03-01",
  "incoterm_location": "Genève",
  "destination": "…",
  "products": [ {"sku": "1234", "quantity": 10, "value": 0} ],
  "master": {
    "numero_tva": "…|null", "monnaie": "…|null",
    "conditions_paiement_jours": 30, "assurance": "…|null",
    "mode_expedition": "…|null", "incoterm": "…|null",
    "lieu_provenance": "…|null", "destination_edi": "…|null",
    "matched": true, "status": "OK"
  },
  "filename": "Commande_x.pdf",
  "confidence": 0.95,
  "quality_note": "…|null"
}
```

### `POST /api/build`  (nouvelle)
- Entrée : `{"rows": [ <record>, … ]}` (auth FUNCTION, même app).
- Sortie : **un Excel consolidé** (binaire xlsx). 1 feuille `CCI`, **1 ligne par
  record**, mêmes colonnes d'en-tête qu'aujourd'hui (19), puis produits en
  colonnes `SKU i / Quantité i / Valeur i` (i = 1..max produits du lot), puis
  diagnostics `Nom du fichier / Confiance / Statut / Note qualité`.
- **Surlignage jaune** : pour chaque ligne, les cellules des **champs master
  data** (Numéro de TVA, Monnaie, Conditions de paiement, Assurance, Mode
  d'expédition, Incoterm, Lieu de provenance, Destination EDI) qui sont **vides**
  sont remplies en **jaune** (signal « à compléter via master data »).

## Détails fonction (cci-function/)

- **schema.py** : ajouter au prompt une règle SKU (« code numérique à 4 chiffres ;
  si tu ne lis pas un code à 4 chiffres fiable, renvoie null »). Mettre
  `"pattern": "^[0-9]{4}$"` sur `products[].sku`.
- **function_app.py** : après extraction+enrichissement, **valider** (renvoyer
  422 si échec) :
  - `is_readable == false`, ou
  - un de {customer_name, partner_reference, requested_delivery_date,
    incoterm_location, destination} vide, ou
  - `products` vide, ou un produit avec `sku` ne respectant pas `^\d{4}$`, ou
    `quantity` non numérique/≤0, ou `value` non numérique/<0 (null interdit ;
    0 autorisé).
  - **Client hors master data ⇒ PAS de 422** (on garde la ligne).
  - Sur 200, renvoyer le **record JSON** ci-dessus (plus de xlsx ici).
- **excel_writer.py** : refactor.
  - Garder la logique de colonnes existante mais l'exposer pour le **multi-ligne**.
  - `build_consolidated_workbook(rows: list[dict]) -> bytes` : calcule le max de
    produits, écrit l'en-tête, 1 ligne/record, applique le surlignage jaune sur
    les cellules master vides. Réutiliser `_safe_cell`, le style d'en-tête, les
    largeurs.
- **models.py** : si utile, helper `record` (dict) depuis OrderExtraction +
  MasterDataFields + filename + diagnostics.
- **Pas de changement** au modèle Claude ni au mécanisme d'appel.

## Logic App `trb-cci-logic` (restructuration)

1. `Initialiser_lignes` : variable `lignes` (Array) = `[]`.
2. `Liste_du_dossier` : `Commandes-PDF` (inchangé).
3. `For_each` **séquentiel** (`concurrency = 1`, pour append sûr) :
   - `Obtenir_le_contenu_du_fichier` (inchangé)
   - `HTTP` POST `/api/extract` (corps = contenu ; renvoie record JSON ou 422)
   - **si 200** : `Ajouter_ligne` (append `@body('HTTP')` à `lignes`) puis
     `Deplacer_vers_Commandes_Done` (runAfter Ajouter_ligne = Succeeded)
   - **si 422** (runAfter HTTP = Failed/TimedOut) : `Deplacer_vers_A_revoir`
4. Après la boucle (runAfter For_each = Succeeded **et** Failed) :
   - `Condition` : `length(variables('lignes')) > 0`
   - si vrai : `HTTP_Build` POST `/api/build` avec `{"rows": @variables('lignes')}`
     → `Creer_fichier_consolide` : créer
     `CCI-Lot-@{formatDateTime(utcNow(),'yyyyMMdd-HHmmss')}.xlsx` dans
     `Uppload-CCI` (corps `@body('HTTP_Build')`, comme l'actuel Create file).

Notes :
- `/api/build` nécessite une clé (FUNCTION). Utiliser la **clé d'hôte** ou la clé
  de la fonction build (récupérée via `az functionapp keys list`).
- Séquentiel : OK pour le volume quotidien (qqs commandes). Si le volume grossit,
  on optimisera la collecte.

## Tests

- **Fonction (déployée)** :
  - `/api/extract` sur le bon PDF → JSON record valide (SKU 4 ch.).
  - `/api/extract` sur le doc caviardé → **422** (champs manquants / SKU non conforme).
  - `/api/build` sur 2 records → Excel 2 lignes, surlignage jaune si master vide.
- **Bout en bout (Logic App)** : lot { bon PDF + doc caviardé } →
  **1 Excel (1 ligne)** dans `Uppload-CCI` ; doc caviardé dans `A-revoir` ;
  bon PDF dans `Commandes-Done`.

## Déploiement

- Fonction : republier l'app (voir `cci-function/DEPLOIEMENT.md`).
- Logic App : via `az rest` (PUT de la définition), méthode déjà utilisée.

## Amendements (après tests bout en bout, 2026-06-26)

- **`incoterm_location` rendu OPTIONNEL** (≠ décision initiale « Strict »). Les
  tests sur les vraies commandes ont montré qu'**aucune** ne porte le « Lieu de
  l'incoterm » → la règle Strict rejetait 100 % des commandes. Validé par
  l'utilisateur. Champs commande obligatoires retenus : `customer_name`,
  `partner_reference`, `requested_delivery_date`, `destination`, + ≥1 produit valide.
- **SKU — nomenclature précisée** : un **n° d'article CLIENT** (même à 4 chiffres,
  ex. « ALP Article No. 2600 ») n'est **pas** un SKU TRB ; une réf produit à 6
  chiffres non plus. L'IA renvoie `null` faute de SKU TRB fiable → A-revoir. Le
  comportement prudent est **correct**. Le vrai correctif (réf produit → SKU TRB)
  nécessite un **catalogue produits** : évolution future, hors de ce lot.
- **Résultat validé** : lot de 5 docs → Excel `CCI-Lot-*.xlsx` à **2 lignes**
  (NOVALP MEDICAL SA / SKU 4204 ; RheinCare / SKU 3100, 3101), cases master vides
  surlignées jaune ; 3 docs (faux fichier, capture caviardée conf. 0.42, ALPINE
  sans SKU TRB) correctement routés en `A-revoir`.

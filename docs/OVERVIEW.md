# TRB CCI — Vue d'ensemble de l'outil

> **Point d'entrée unique.** Ce document explique ce que fait l'outil, comment il
> fonctionne de bout en bout, et **où se trouve chaque donnée, script et sortie**.
> À lire en premier — que tu sois un humain qui reprend le projet ou un assistant
> IA qui ouvre une nouvelle session.
>
> Dernière mise à jour : 2026-07-01.

---

## 1. À quoi sert l'outil (en une phrase)

Automatiser la saisie des **commandes clients** de TRB Chemedica (Genève) : lire un
document de commande (PDF / image, même manuscrit), en extraire les infos utiles
avec l'IA (Claude), **retrouver le code client et corriger les codes produit (SKU)**
en s'appuyant sur l'historique des ventes, et produire un **fichier Excel CCI** prêt
à importer dans l'ERP (ProConcept).

Le but : transformer une commande papier/PDF hétérogène en une ligne Excel propre,
avec le bon **code Customer (« Clé 1 »)** et les bons **SKU**, ou la router vers une
**revue manuelle** si quelque chose ne colle pas.

---

## 2. Les deux sous-systèmes du dépôt

Le dépôt contient **deux** applications distinctes. Ne pas les confondre.

| | **A. App web Next.js** (racine `src/`) | **B. Fonction Azure CCI** (`cci-function/`) ⭐ |
|---|---|---|
| Rôle | Interface navigateur : glisser-déposer des commandes, table éditable, export Excel | Pipeline serveur (API) : 1 requête/document → record JSON → Excel CCI consolidé |
| Statut | Prototype / démo local (`npm run dev`) | **En production sur Azure** — c'est l'outil « CCI » actif |
| IA | Claude, 1 appel (extraction) | Claude, **2 appels** (extraction + résolution master data) |
| Sortie | `.xlsx` 2 feuilles (Orders / Order Lines) | `.xlsx` CCI 1 feuille consolidée |
| Doc | `CLAUDE.md` (racine) | **ce document** + `cci-function/README.md` + `cci-function/DEPLOIEMENT.md` |

⭐ **Le travail récent et la production concernent la fonction Azure CCI** (partie B).
Le reste de ce document décrit la partie B, sauf mention contraire.

---

## 3. Le pipeline CCI de bout en bout

```
Commande (PDF / PNG / JPEG / TIFF)
        │
        ▼
[Logic App / Power Automate]  ── 1 document par appel ──►  POST /api/extract
        │                                                        │
        │   ┌────────────────────────────────────────────────────┘
        │   ▼
        │  1. Extraction (Claude, appel n°1)
        │     → nom client, référence partenaire, date de livraison,
        │       et par ligne : désignation + SKU + quantité
        │  2. Validation de FORMAT (sinon 422 « A-revoir »)
        │  3. Résolution master data (Claude, appel n°2)
        │     → Clé 1 (code Customer) + SKU validés/corrigés via le catalogue du client
        │  4. Validation STRICTE (client introuvable / produit hors catalogue → 422 « A-revoir »)
        │  5. Renvoie un record JSON (200)
        │
        ▼
[Logic App agrège les records du lot]  ──►  POST /api/build
                                                 │
                                                 ▼
                                    Excel CCI consolidé (1 ligne/commande)
                                                 │
                                                 ▼
                                 Dépôt SharePoint de sortie → import ERP ProConcept
```

- **1 document = 1 appel `/api/extract`** : isole les échecs, permet le rejet unitaire.
- **`/api/build`** agrège tous les records d'un lot en **un seul** Excel.
- **« A-revoir » (HTTP 422)** = la commande n'a pas pu être traitée automatiquement
  (illisible, client introuvable, produit hors catalogue…) → routée vers revue humaine.
- Détail du branchement Logic App / SharePoint : voir [`HANDOFF-logic-app.md`](HANDOFF-logic-app.md).

---

## 4. Où se trouve chaque chose (carte du dépôt)

### 4.1 Code de la fonction CCI (`cci-function/`)

| Fichier | Rôle |
|---|---|
| `function_app.py` | Points d'entrée HTTP `/api/extract` et `/api/build` ; orchestration du flux. |
| `app/schema.py` | **Cœur du comportement IA** : prompts système + outils Claude (`extract_order`, `resolve_order`). C'est ici qu'on édite ce qui est extrait/résolu. |
| `app/anthropic_client.py` | Les 2 appels Claude (`extract_order`, `resolve_order`). Modèle centralisé, cache de prompt sur la master data. |
| `app/resolver.py` | Orchestration de la résolution : appel Claude + **garde-fou anti-hallucination** (un SKU/code n'est retenu que s'il existe vraiment dans la master data). |
| `app/enrichment.py` | Chargement de la master data (`clients` + `catalogue`) et rendu du contexte envoyé à Claude. |
| `app/models.py` | Contrat de données (`OrderExtraction`, `ProductLine`, `Resolution`), validations (`validate_order`, `validate_resolution`), `build_record`. |
| `app/excel_writer.py` | Génération de l'Excel CCI (mono `build_workbook` et consolidé `build_consolidated_workbook`). |
| `app/config.py` | Constantes (modèle Claude via `ANTHROPIC_MODEL`, `MAX_TOKENS`). |
| `selftest.py` | Test local **sans API** (résolution simulée) : mapping + garde-fou + Excel. |

### 4.2 Données, scripts, sorties

| Chemin | Type | Description |
|---|---|---|
| `cci-function/app/master_data.xlsx` | **Donnée (committée)** | La master data utilisée à l'exécution. 2 feuilles : `clients` (87 lignes : `customer_code`, `nom_client`) et `catalogue` (840 lignes : `customer_code`, `sku`, `designation`). |
| `cci-function/tools/build_master_data.py` | **Script** | Génère `master_data.xlsx` depuis un export de ventes (déduplication). |
| `cci-function/tools/ventes_source.xlsx` | **Donnée brute (NON committée, `.gitignore`)** | Export de ventes source (`data` : N° doc, Description courte, Référence principale=SKU, Date, Clé 1, Nom 1, Quantité). Fournie manuellement, sert d'entrée au script ci-dessus. |
| `cci-function/sample_commande.png` | **Donnée de test** | Exemple de commande (client fictif « Pharmacie Centrale SA » → renvoie 422, normal). |
| `cci-function/*.out.xlsx` | **Sorties de test (NON committées)** | Résultats de `selftest.py` / tests manuels. |
| `Donnees_CCI.xlsx` (racine) | **Donnée de référence** | Spécification du format de colonnes CCI/ProConcept (référence historique). |
| `TRB_Ventes_2022-2026_PowerBI (1).xlsx` (racine) | **Donnée (non utilisée par l'outil)** | Modèle en étoile Power BI (Ventes + Dim_Client/SKU/Produit). **N'est PAS la master data** (les SKU y sont vides à ~90 %). Conservé pour analyse, pas branché au pipeline. |

### 4.3 Documentation

| Fichier | Contenu |
|---|---|
| `docs/OVERVIEW.md` | **Ce document** — vue d'ensemble et carte du dépôt. |
| `cci-function/README.md` | Guide d'installation / test local / déploiement / refresh master data. |
| `cci-function/DEPLOIEMENT.md` | Référence de l'instance Azure en service (URL, clés, re-déploiement). |
| `docs/HANDOFF-logic-app.md` | Branchement Logic App / SharePoint (orchestration en amont/aval). |
| `docs/superpowers/specs/*.md` | Specs de conception historiques (fonction Azure, consolidation par lot). |
| `CLAUDE.md` (racine) | Instructions projet (surtout l'app web Next.js) + conventions. |

---

## 5. Ce qui est lu sur la commande (extraction)

L'outil n'extrait du document **QUE** ceci (défini dans `app/schema.py`) :

- **nom du client** (`customer_name`)
- **référence partenaire** (`partner_reference`) = n° de commande fournisseur
- **date de livraison souhaitée** (`requested_delivery_date`)
- pour **chaque ligne produit** : **désignation** (nom produit), **SKU** (4 chiffres, tel qu'écrit), **quantité**

Le SKU envoyé par le client est souvent faux ou absent : **ce n'est pas grave**, il
est corrigé à l'étape suivante via la désignation. Tout le reste (TVA, monnaie,
incoterm, adresse…) n'est **pas** extrait.

---

## 6. La master data et la résolution (le cœur métier)

### 6.1 D'où vient la master data
Générée depuis l'historique des ventes (`tools/ventes_source.xlsx`) par
`tools/build_master_data.py`, dédupliquée en 2 tables :
- **`clients`** : `customer_code` (Clé 1, 7 chiffres) ↔ `nom_client`.
- **`catalogue`** : par client, la liste `sku` (4 chiffres) + `designation` des
  produits qu'il achète réellement (1 ligne par couple client-SKU).

### 6.2 Ce que fait la résolution (Claude, appel n°2)
On envoie à Claude la master data (clients + catalogues, **mise en cache**) + la
commande extraite. Claude :
1. **retrouve le client** par son nom (les noms diffèrent souvent : casse, forme
   juridique, abréviations…) → renvoie sa **Clé 1** ;
2. pour chaque ligne, **valide/corrige le SKU** en le comparant au catalogue **de ce
   client** :
   - `ok` = le SKU du client est déjà correct,
   - `corrige` = SKU faux/absent remplacé par le bon (retrouvé via la désignation),
   - `inconnu` = ni le SKU ni la désignation ne matchent le catalogue du client.

**Garde-fou** (`resolver.py`) : un code ou un SKU renvoyé par Claude n'est accepté
que s'il **existe réellement** dans la master data. Impossible d'inventer un SKU.

### 6.3 Règle de rejet stricte (« A-revoir »)
Rejet en **422** (revue manuelle) si :
- le **client est introuvable** dans la master data, **ou**
- **au moins un produit** est hors du catalogue du client.

Sinon → record 200 avec Clé 1 remplie et SKU corrigés.

---

## 7. Le fichier Excel CCI produit

Une ligne par commande. Colonnes (voir `app/excel_writer.py`) :

```
Nom du client | Clé 1 | Référence partenaire | Date de livraison souhaitée |
(SKU i | Quantité i | SKU i (statut))  ×  nb de produits |
Nom du fichier | Confiance | Statut | Note qualité
```

- **Clé 1** = code Customer résolu.
- **SKU i** = le SKU **corrigé** (déliverable ERP) ; **SKU i (statut)** = `ok` / `corrige`.
- Les **SKU corrigés** sont **surlignés en jaune** pour revue rapide.

---

## 8. Déploiement & exploitation (Azure)

| | |
|---|---|
| Function App | `trb-cci-extraction-ae73fa` (groupe `trb-cci-rg`, région `switzerlandnorth`) |
| Endpoints | `https://trb-cci-extraction-ae73fa.azurewebsites.net/api/{extract,build}` (auth par clé `?code=…`) |
| Clé API Claude | `ANTHROPIC_API_KEY` dans les Application Settings Azure (jamais dans le code) |
| Déployer | `cd cci-function && func azure functionapp publish trb-cci-extraction-ae73fa --build remote` |
| Pas de CI/CD | Pousser sur GitHub **ne** met **pas** à jour Azure — le déploiement est manuel. |

> Re-auth Azure (le jeton TRB expire toutes les ~48 h) : voir `DEPLOIEMENT.md` et la
> mémoire projet `azure-cci-deploy`.

### Rafraîchir la master data
```bash
cd cci-function
python3 tools/build_master_data.py /chemin/vers/nouvel_export_ventes.xlsx
func azure functionapp publish trb-cci-extraction-ae73fa --build remote
```

### Tester en local (sans API)
```bash
cd cci-function && python3 selftest.py
```

---

## 9. Contrat HTTP (résumé)

**`POST /api/extract`** — 1 document (corps brut, type via `Content-Type`/`?filename=`).
- `200` : record JSON (voir ci-dessous)
- `422` : « A-revoir » + `raison` (illisible / client introuvable / produit hors catalogue)
- `400` fichier vide/non supporté · `500` clé API absente · `502` réponse Claude inattendue

Record JSON (contrat consommé par le Logic App / `/api/build`) :
```json
{
  "customer_name": "…", "partner_reference": "…", "requested_delivery_date": "…",
  "customer_code": "2780008",
  "products": [{"designation":"…","sku":"1311","input_sku":"9999","sku_status":"corrige","quantity":100}],
  "resolution": {"customer_code":"2780008","customer_name_master":"…","matched":true,"status":"OK (1 SKU corrigé)"},
  "filename": "…", "confidence": 0.92, "quality_note": null
}
```

**`POST /api/build`** — `{"rows": [<record>, …]}` → Excel CCI consolidé (`.xlsx`).

> ⚠️ Ce record a remplacé l'ancien bloc `master` (TVA/monnaie/incoterm, supprimé).
> Tout consommateur en aval (Logic App) doit lire `customer_code` et
> `products[].sku` / `sku_status`.

---

## 10. Glossaire

- **Clé 1** — le code Customer (7 chiffres) du client dans l'ERP. Résolu par l'IA depuis le nom.
- **SKU** — code article à 4 chiffres (dans la source de ventes : colonne « Référence principale »).
- **Désignation** — nom du produit tel qu'écrit ; sert à retrouver le bon SKU.
- **Catalogue (d'un client)** — la liste des produits (SKU + désignation) qu'un client achète.
- **A-revoir** — statut de rejet (HTTP 422) : à traiter manuellement.
- **Master data** — `clients` + `catalogue`, dérivés de l'historique des ventes.
- **Record** — l'objet JSON renvoyé par `/api/extract`, agrégé par `/api/build`.

---

## 11. Historique & évolutions prévues

- L'enrichissement TVA/monnaie/incoterm d'origine a été **supprimé** ; la master data
  sert désormais uniquement à **Clé 1 + validation/correction SKU**.
- Prochaines pistes : externaliser la master data (SharePoint/ERP) plutôt que la
  bundler ; tableau de bord de confiance ; boucle de revue humaine.

# Azure Function — Extraction de commandes → Excel CCI (ProConcept)

**Date :** 2026-06-23
**Statut :** Conception validée (en attente de relecture)

## Objectif

Créer une **Azure Function HTTP** (Python) qui, à partir d'un document de commande
fournisseur (PDF / image), produit un fichier Excel contenant les **données d'une
CCI (Commande Client Interne)** pour saisie dans l'ERP **ProConcept**.

Place dans le flux global :

```
Mail → Power Automate (dépôt pièce jointe SharePoint)
     → POST fichier vers Azure Function
        → Claude extrait les données du document (JSON)
        → enrichissement via master data (client → TVA, monnaie, incoterm…)
        → openpyxl écrit l'Excel (format forcé, déterministe)
     → réponse = fichier .xlsx
     → Power Automate dépose le .xlsx dans un autre dossier SharePoint
```

Ce document ne couvre **que l'Azure Function**. Power Automate et SharePoint
seront configurés ensuite.

## Principe directeur

**Claude n'écrit jamais l'Excel.** Claude renvoie uniquement des données
structurées (JSON, via un *forced tool call*). C'est le **code Python** qui
construit le fichier Excel en imposant mécaniquement les colonnes et leur ordre.
Cela garantit un format déterministe et constant, indépendant de la sortie du
modèle.

## Sources des données (les 22 points de `Donnees_CCI.xlsx`)

La colonne « Source » du fichier de spécification définit trois catégories :

### A. Extrait du document par Claude (Source = `Commande`)

| # | Donnée | Champ JSON | Format |
|---|--------|-----------|--------|
| 3 | Nom du client / partenaire | `customer_name` *(clé de jointure master data)* | texte |
| 4 | Référence partenaire (n° commande fournisseur) | `partner_reference` | n° |
| 9 | Date de livraison souhaitée | `requested_delivery_date` | JJ.MM.AAAA |
| 15 | Lieu de l'incoterm | `incoterm_location` | texte/lieu |
| 17 | Destination | `destination` | texte/adresse |
| 20 | SKU (une par ligne produit) | `products[].sku` | code SKU |
| 21 | Quantité | `products[].quantity` | nombre |
| 22 | Valeur du SKU (**0 est valide**) | `products[].value` | montant ≥ 0 |

Champs de diagnostic également renvoyés par Claude : `confidence` (0..1),
`is_readable` (bool), `quality_note` (texte), `comments` (résumé des remarques).

> La devise et les conditions de paiement peuvent être lues dans le document pour
> recoupement, mais la **valeur autoritative vient du master data** (voir B).

### B. Master data embarqué (Source = `Master Data`, jointure sur le **nom du client**)

| # | Donnée | Origine |
|---|--------|---------|
| 1 | Type de document (gabarit) | constante : `Commande Client` |
| 2 | Description gabarit | constante : `Vente - Commande Client` |
| 5 | Numéro de TVA | master data |
| 6 | Monnaie comptable | master data |
| 7 | Conditions de paiement (jours) | master data |
| 8 | Assurance | master data |
| 13 | Mode d'expédition | master data |
| 14 | Incoterm | master data |
| 16 | Lieu de provenance | master data |
| 18 | Destination EDI | master data |

### C. À déterminer (Source = `À déterminer`) → colonnes présentes mais vides

#10 Délai de disponibilité · #11 Délai d'expédition · #12 Délai de livraison ·
#19 Stock logique.

## Master data embarqué

Fichier `master_data.xlsx` livré **avec** la fonction (remplaçable plus tard par
SharePoint / l'ERP). Feuille `partenaires`, **clé = nom du client** :

```
nom_client | numero_tva | monnaie | conditions_paiement_jours | assurance | mode_expedition | incoterm | lieu_provenance | destination_edi
```

- Jointure par nom **normalisé** (minuscules, espaces réduits, accents tolérés).
- Client introuvable → ces colonnes restent vides + colonne `statut` annotée
  « client introuvable dans le master data » + log d'avertissement.
- Livré avec 2-3 lignes d'exemple à compléter par l'utilisateur.

**Extensibilité de la jointure.** La clé est le nom du client *pour l'instant*,
mais certaines données dépendront aussi du **produit** ou d'autres critères. Le
module `enrichment.py` est donc conçu comme un point unique où l'on ajoute des
tables/clés de jointure (par client, par produit, …) sans toucher au reste du
code. Les tables définitives seront figées dans un second temps (le fichier
master data n'est pas encore arrêté).

## Format de l'Excel de sortie

**Une ligne par commande** (un document = un appel = une ligne de données).
Les produits sont étalés en groupes de colonnes (SKU 1, SKU 2, …), comme l'app
Next.js existante. Ordre des colonnes calqué sur la spec (#1 → #22), suivi de
colonnes de diagnostic.

Colonnes d'en-tête (une fois) :

```
Type de document | Description gabarit | Nom du client | Référence partenaire |
Numéro de TVA | Monnaie comptable | Conditions de paiement (jours) | Assurance |
Date de livraison souhaitée | Délai de disponibilité | Délai d'expédition |
Délai de livraison | Mode d'expédition | Incoterm | Lieu de l'incoterm |
Lieu de provenance | Destination | Destination EDI | Stock logique |
```

Puis, pour chaque produit n : `SKU n | Quantité n | Valeur n`.

Puis diagnostic : `Nom du fichier | Confiance | Statut | Note qualité`.

- Anti-injection de formules : toute chaîne commençant par `= + - @ \t \r` est
  préfixée d'une apostrophe (reprise de la logique de `excel.ts`). Les nombres
  ne sont jamais altérés.
- Feuille unique nommée `CCI`.

## Contrat HTTP

### Entrée
- `POST`, **fichier brut dans le corps** de la requête.
- Type détecté via l'en-tête `Content-Type` (`application/pdf`, `image/png`,
  `image/jpeg`, `image/tiff`) ou un paramètre `?filename=` en query (extension).
- **TIFF** converti en PNG côté Python (Pillow) — Claude vision n'accepte pas le TIFF.
- Le nom de fichier (query `?filename=` ou en-tête `Content-Disposition`) est
  conservé pour les logs et la colonne « Nom du fichier ».

### Sortie
- Succès : `200`, corps = fichier `.xlsx`,
  `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
  `Content-Disposition: attachment; filename="CCI-<horodatage>.xlsx"`.
- Erreurs (JSON `{ "error": "...", "fichier": "...", ... }`) :
  - `400` — corps vide / type de fichier non supporté / fichier illisible techniquement.
  - `422` — **document jugé illisible par Claude** (`is_readable=false`) : le JSON
    nomme le fichier problématique et donne la raison + la confiance, pour router
    vers une revue manuelle.
  - `500` — `ANTHROPIC_API_KEY` absente / erreur interne.
  - `502` — réponse Claude inattendue (refus, pas de `tool_use`).

## Architecture du projet

Modèle de programmation **Azure Functions Python v2** (décorateurs, un seul
`function_app.py` — modèle moderne).

```
cci-function/
  function_app.py            # HTTP trigger : orchestration + gestion d'erreurs + logs
  app/
    __init__.py
    schema.py                # prompt système + définition du tool "extract_order"
    anthropic_client.py      # un appel Claude → JSON typé (forced tool call) + normalize()
    enrichment.py            # jointure master data (nom client → TVA, monnaie, incoterm…)
    excel_writer.py          # openpyxl : colonnes forcées, anti-injection, déterministe
    models.py                # dataclasses (OrderExtraction, ProductLine) = contrat de données
    config.py                # constantes (type doc, modèle, noms de colonnes)
    master_data.xlsx         # données de référence (phase de test)
  requirements.txt           # azure-functions, anthropic, openpyxl, pillow
  host.json                  # config hôte + extension bundle
  local.settings.json        # dev local (gitignored) — contient ANTHROPIC_API_KEY
  local.settings.json.example
  .funcignore
  .gitignore
  README.md                  # déploiement Azure + test manuel pas à pas
```

Décisions clés (reprises de l'app Next.js existante) :
- **Forced tool call** (`tool_choice: {type:"tool", name:"extract_order"}`) → la
  réponse est toujours un bloc `tool_use` typé.
- **`normalize()`** défensif → un objet bien formé est garanti même si le modèle
  omet des champs.
- **Un document par requête** → isole les pannes (un mauvais scan ne fait pas
  échouer le lot), permet statut/retry par document côté Power Automate.
- Modèle Claude centralisé (`config.py`, surchargable par variable
  d'environnement `ANTHROPIC_MODEL`). Cible : dernier Claude Sonnet.

## Sécurité de la clé API

- Lue **exclusivement** depuis la variable d'environnement `ANTHROPIC_API_KEY`,
  jamais en dur.
- En local : `local.settings.json` (gitignored).
- Sur Azure : **Application Settings** de la Function App (ou Key Vault plus tard).
- `local.settings.json.example` fourni sans secret.

## Gestion d'erreurs & logs

- `logging` standard Python à chaque étape : réception fichier (nom, taille,
  type), appel Claude, confiance/lisibilité, jointure master data (trouvé/non
  trouvé), génération Excel, réponse.
- Toute exception attrapée → réponse HTTP propre (codes ci-dessus), jamais de
  stack trace renvoyée au client.

## Plan de déploiement & de test (détaillé à l'implémentation)

1. **Test local** : `func start`, puis appel manuel avec `curl` (envoi d'un PDF
   en corps brut) → vérifier le `.xlsx` renvoyé.
2. **Déploiement Azure** : création d'une Function App (Python 3.11, plan
   Consumption), publication via VS Code (extension Azure Functions) ou
   `func azure functionapp publish`, configuration de `ANTHROPIC_API_KEY` dans
   les Application Settings, récupération de l'URL + clé de fonction.
3. **Test à distance** : même `curl` sur l'URL Azure, avant de brancher Power
   Automate.

## Hors périmètre (pour plus tard)

- Power Automate et SharePoint.
- Master data depuis SharePoint / API ERP (interface prévue, jointure isolée
  dans `enrichment.py`).
- Champs « À déterminer » (#10-12, #19).
- Matching flou des noms de clients, code TVA via fournisseur, dashboard de
  confiance, revue humaine.

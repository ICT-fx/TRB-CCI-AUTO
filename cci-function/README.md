# Azure Function — Extraction de commandes → Excel CCI

Cette fonction reçoit un document de commande (PDF ou image), en extrait les
données via Claude, les enrichit avec un fichier de référence (master data), et
renvoie un fichier Excel au format CCI (ProConcept).

> Conception détaillée : voir
> `../docs/superpowers/specs/2026-06-23-cci-azure-function-design.md`.

---

## 1. Ce dont tu as besoin

- **Python 3.11** (Azure Functions Python tourne en 3.11).
- **Azure Functions Core Tools v4** — l'outil `func` pour tester en local et
  publier. Installation (macOS, avec Homebrew) :
  ```bash
  brew tap azure/functions
  brew install azure-functions-core-tools@4
  ```
- **Azure CLI** — l'outil `az` pour créer les ressources Azure :
  ```bash
  brew install azure-cli
  ```
- Une **clé API Anthropic** (commence par `sk-ant-…`).
- Un **compte Azure** (l'offre gratuite suffit pour tester).

> Tu n'as encore rien sur Azure ? C'est normal. La section 5 crée tout.

---

## 2. Test rapide SANS clé API (cœur déterministe)

Pour vérifier l'enrichissement master data + la génération Excel sans rien
appeler :

```bash
cd cci-function
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 selftest.py
```

Ça produit `selftest.out.xlsx` et affiche les colonnes. Si tu vois
« OK — tous les contrôles passent », le cœur fonctionne.

---

## 3. Configurer la clé API (en local, en sécurité)

La clé est lue **uniquement** depuis une variable d'environnement, jamais en dur.

1. Copie le modèle :
   ```bash
   cp local.settings.json.example local.settings.json
   ```
2. Ouvre `local.settings.json` et remplace `sk-ant-REMPLACER-PAR-TA-CLE` par ta
   vraie clé.

⚠️ `local.settings.json` est dans `.gitignore` : il ne sera **jamais** committé.
Ne mets jamais ta clé ailleurs.

---

## 4. Lancer et tester en local

```bash
cd cci-function
source .venv/bin/activate          # si pas déjà actif
func start
```

`func` affiche une URL du type :
`http://localhost:7071/api/extract`

Dans un **autre terminal**, envoie-lui un PDF de commande (le fichier brut dans
le corps de la requête) :

```bash
curl -X POST \
  "http://localhost:7071/api/extract?filename=ma_commande.pdf" \
  -H "Content-Type: application/pdf" \
  --data-binary @"/chemin/vers/ma_commande.pdf" \
  --output resultat.xlsx
```

Ouvre `resultat.xlsx` : tu dois voir une ligne avec les données de la commande.

Pour une image :
```bash
curl -X POST \
  "http://localhost:7071/api/extract?filename=scan.png" \
  -H "Content-Type: image/png" \
  --data-binary @"/chemin/vers/scan.png" \
  --output resultat.xlsx
```

> Si le document est jugé illisible, tu reçois une réponse JSON (code 422) qui
> nomme le fichier — c'est voulu (à router vers une revue manuelle).
> Pour voir les codes/messages d'erreur, enlève `--output resultat.xlsx` et
> ajoute `-i` pour afficher les en-têtes.

---

## 5. Déployer sur Azure (pas à pas)

### 5.1 Se connecter

```bash
az login
```

### 5.2 Créer les ressources

Choisis un **nom unique** pour la fonction (lettres/chiffres, unique sur tout
Azure), par ex. `trb-cci-extraction-001`. Adapte les variables ci-dessous :

```bash
# Variables (à adapter)
RG="trb-cci-rg"                       # groupe de ressources
LOCATION="westeurope"                 # région
STORAGE="trbccistorage001"            # 3-24 lettres/chiffres minuscules, unique
APP="trb-cci-extraction-001"          # nom de la Function App, unique

# 1) Groupe de ressources
az group create --name "$RG" --location "$LOCATION"

# 2) Compte de stockage (requis par Azure Functions)
az storage account create \
  --name "$STORAGE" --resource-group "$RG" \
  --location "$LOCATION" --sku Standard_LRS

# 3) La Function App (Python 3.11, plan Consumption = payé à l'usage)
az functionapp create \
  --name "$APP" --resource-group "$RG" \
  --storage-account "$STORAGE" \
  --consumption-plan-location "$LOCATION" \
  --runtime python --runtime-version 3.11 \
  --functions-version 4 --os-type Linux
```

### 5.3 Configurer la clé API sur Azure (en sécurité)

La clé vit dans les **Application Settings** de la Function App (chiffrées, pas
dans le code) :

```bash
az functionapp config appsettings set \
  --name "$APP" --resource-group "$RG" \
  --settings ANTHROPIC_API_KEY="sk-ant-TA-VRAIE-CLE" \
             ANTHROPIC_MODEL="claude-sonnet-4-6"
```

### 5.4 Publier le code

Depuis le dossier `cci-function/` :

```bash
cd cci-function
func azure functionapp publish "$APP"
```

À la fin, `func` affiche l'**URL d'invocation**, du type :
`https://trb-cci-extraction-001.azurewebsites.net/api/extract`

### 5.5 Récupérer la clé de fonction

L'URL est protégée par une clé. Récupère-la :

```bash
az functionapp function keys list \
  --name "$APP" --resource-group "$RG" \
  --function-name extract
```

(ou : Portail Azure → ta Function App → Functions → `extract` → « Function Keys ».)

---

## 6. Tester la fonction déployée (avant Power Automate)

Avec l'URL et la clé récupérées :

```bash
curl -X POST \
  "https://trb-cci-extraction-001.azurewebsites.net/api/extract?filename=ma_commande.pdf&code=TA_CLE_DE_FONCTION" \
  -H "Content-Type: application/pdf" \
  --data-binary @"/chemin/vers/ma_commande.pdf" \
  --output resultat.xlsx
```

Si tu récupères un `resultat.xlsx` correct, la fonction est prête à être branchée
sur Power Automate.

---

## 7. Modifier le master data

Le fichier de référence est `app/master_data.xlsx`, feuille `partenaires`.
Colonnes (la 1re est la clé de jointure) :

```
nom_client | numero_tva | monnaie | conditions_paiement_jours | assurance | mode_expedition | incoterm | lieu_provenance | destination_edi
```

Ajoute/édite des lignes, enregistre, et **re-publie** (`func azure functionapp
publish "$APP"`). La jointure ignore la casse et les accents, mais le nom doit
correspondre au client lu sur le document.

---

## 8. Contrat HTTP (résumé)

| | |
|---|---|
| **Méthode** | `POST` |
| **Entrée** | fichier brut dans le corps ; type via `Content-Type` ou `?filename=` |
| **Types** | PDF, PNG, JPEG, TIFF (TIFF converti en PNG automatiquement) |
| **Succès** | `200` + fichier `.xlsx` dans le corps |
| **Document illisible** | `422` + JSON nommant le fichier (revue manuelle) |
| **Fichier vide / type non supporté** | `400` + JSON |
| **Clé API absente** | `500` + JSON |
| **Réponse Claude inattendue** | `502` + JSON |

---

## 9. Et ensuite ?

Une fois ce test validé, on configurera **Power Automate** pour :
appeler cette URL avec la pièce jointe → récupérer le `.xlsx` renvoyé → le
déposer dans le dossier SharePoint de sortie.

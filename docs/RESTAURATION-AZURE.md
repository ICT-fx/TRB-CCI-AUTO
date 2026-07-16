# Restauration Azure — remettre en place l'outil CCI après ré-abonnement

> **Contexte.** L'abonnement Azure (`Azure subscription 1`,
> `5e207121-3672-4bd2-a92e-bb03285123d9`, tenant TRB Chemedica International SA)
> a été arrêté vers mi-juillet 2026. Toutes les ressources Azure ont donc été
> supprimées. Ce document + le dossier local **`azure-backup/`** (non committé,
> contient les secrets) permettent de **tout reconstruire**.
>
> Sauvegarde effectuée le **2026-07-16**, alors que tout était encore en service.
> Ce travail sera probablement refait par Claude Code : ce document est écrit
> pour être suivi par un humain **ou** collé en contexte d'une session Claude.

---

## 1. Ce qui a été perdu vs ce qui est conservé

| | État |
|---|---|
| **Code de la fonction** (`cci-function/`) | ✅ Conservé — dans ce dépôt Git (GitHub `origin/main`) |
| **Master data** (réelle + démo) | ✅ Conservée — `cci-function/app/master_data.xlsx` (démo) et `master_data.REEL.backup.xlsx` (réelle) |
| **Clé API Anthropic** | ✅ Conservée — `cci-function/local.settings.json` (non committé, local) et copie dans `azure-backup/21-functionapp-appsettings.json` |
| **SharePoint** (dossiers + fichiers) | ✅ Conservé — SharePoint fait partie de Microsoft 365, PAS de l'abonnement Azure. Rien à refaire côté SharePoint. |
| Function App `trb-cci-extraction-ae73fa` | ❌ Supprimée — config sauvegardée dans `azure-backup/2x-*.json` |
| **Logic App `trb-cci-logic`** (l'automatisation) | ❌ Supprimée — **définition complète** sauvegardée dans `azure-backup/40-logicapp-definition.json` |
| Connexion API SharePoint | ❌ Supprimée — à recréer + ré-autoriser (OAuth) ; sauvegarde `azure-backup/51-connection-sharepointonline.json` |
| Compte de stockage `trbccistae73fa` | ❌ Supprimé — ne contenait que la plomberie interne des Functions, rien à récupérer |
| Clés d'appel de la fonction (`?code=…`) | ❌ Invalidées — de **nouvelles** clés seront générées ; sauvegarde des anciennes dans `azure-backup/22-functionapp-keys.json` (pour référence uniquement) |

## 2. Ce qui existait (inventaire au 2026-07-16)

Un seul groupe de ressources, **`trb-cci-rg`**, région **`switzerlandnorth`** :

| Ressource | Type | Rôle |
|---|---|---|
| `trb-cci-extraction-ae73fa` | Function App (Linux, **Python 3.11**, Functions **v4**, plan Consumption Y1) | Les 3 endpoints HTTP : `POST /api/extract`, `POST /api/build`, `POST /api/build_errors` (auth par clé d'hôte `?code=…`) |
| `trb-cci-logic` | Logic App Consumption | L'automatisation : tous les jours à **15h** (fuseau « Romance Standard Time ») + déclenchement manuel |
| `sharepointonline` | Connexion API | Connecteur SharePoint du Logic App, autorisé par `fantin.schellekens@trbchemedica.com` |
| `trbccistae73fa` | Storage StandardLRS StorageV2 | Stockage interne requis par la Function App |
| `SwitzerlandNorthLinuxDynamicPlan` | App Service Plan Y1 | Créé automatiquement avec la Function App |

**App settings de la Function App** (valeurs dans `azure-backup/21-…json`) :
`ANTHROPIC_API_KEY` (= celle de `cci-function/local.settings.json`),
`ANTHROPIC_MODEL` = `claude-sonnet-4-6`, + settings système (`AzureWebJobsStorage`…)
recréés automatiquement.

**Ce que fait la Logic App** (définition exacte : `azure-backup/40-logicapp-definition.json`) :
1. Déclencheur `Recurrence` : 1×/jour à 15h.
2. `Liste_du_dossier` : liste le dossier SharePoint d'entrée `Commandes-PDF`.
3. `For_each` **séquentiel** (concurrency = 1) sur chaque fichier :
   `Obtenir_le_contenu_du_fichier` → `HTTP` POST `/api/extract?filename=…&code=…` ;
   si **200** → `Ajouter_ligne` + `Creer_dans_Done` + `Supprimer_original_Done` ;
   si **422** → `Ajouter_erreur` + `Creer_dans_A_revoir` + `Supprimer_original_A_revoir`.
4. `Condition_lignes` : s'il y a des lignes → `HTTP_Build` POST `/api/build` →
   crée `CCI-Lot-AAAAMMJJ-HHMMSS.xlsx` dans `Uppload-CCI`.
5. `Condition_erreurs` : s'il y a des rejets → `HTTP_Build_erreurs` POST
   `/api/build_errors` → fichier récap des « A-revoir ».

**SharePoint** (inchangé, rien à recréer) : site
`https://trbchemedica0.sharepoint.com/sites/HQSupply`, bibliothèque `Smart_Supply`,
dossier `Entrees-de-commandes` avec `Commandes-PDF` (entrée), `Uppload-CCI`
(sortie), `Commandes-Done` (archive), `A-revoir` (rejets).

## 3. Contenu du dossier `azure-backup/` (local, gitignoré — SECRETS)

| Fichier | Contenu |
|---|---|
| `00-…` à `02-…` | Souscription, groupes, liste des ressources |
| `10-arm-template-trb-cci-rg.json` | Template ARM complet du groupe (référence de config) |
| `20-…` à `26-…` | Function App : définition, **app settings (avec la clé Anthropic)**, **clés de fonction**, config, plan, liste des fonctions |
| `30-…`, `31-…` | Compte de stockage + **ses clés** |
| `40-logicapp-definition.json` | ⭐ **La définition complète de la Logic App** (avec l'ancienne clé de fonction dans les URL) |
| `50-…`, `51-…` | Connexions API (SharePoint) |
| `60-…` | Application Insights (aucun) |
| `export_azure.sh` | Le script qui a produit ces exports (réutilisable) |

> ⚠️ Ne jamais committer ce dossier (il est dans `.gitignore`). En faire une copie
> sur un support sûr (disque externe / coffre) est une bonne idée.

## 4. Procédure de restauration pas-à-pas

Prérequis : `az` (Azure CLI) et `func` (Azure Functions Core Tools) installés —
c'est déjà le cas sur ce Mac. Nouvel abonnement actif.

### 4.1 Connexion

```bash
az login   # ou, depuis Claude Code (non interactif) :
# script -q /dev/null az login --use-device-code --only-show-errors  (en tâche de fond,
# sandbox désactivée ; se termine par un EOFError SANS gravité — le token est en cache)
az account set --subscription "<ID de la nouvelle souscription>"
```

### 4.2 Groupe, stockage, Function App

Le nom d'une Function App est un **domaine global** : reprendre
`trb-cci-extraction-ae73fa` si disponible (probable), sinon choisir un nouveau
suffixe et adapter partout.

```bash
az group create -n trb-cci-rg -l switzerlandnorth

az storage account create -n trbccistae73fa -g trb-cci-rg \
  -l switzerlandnorth --sku Standard_LRS

az functionapp create -n trb-cci-extraction-ae73fa -g trb-cci-rg \
  --consumption-plan-location switzerlandnorth \
  --runtime python --runtime-version 3.11 --functions-version 4 \
  --os-type Linux --storage-account trbccistae73fa
```

### 4.3 App settings (la clé Anthropic)

```bash
# La valeur d'ANTHROPIC_API_KEY est dans cci-function/local.settings.json
az functionapp config appsettings set -n trb-cci-extraction-ae73fa -g trb-cci-rg \
  --settings "ANTHROPIC_API_KEY=<valeur>" "ANTHROPIC_MODEL=claude-sonnet-4-6"
```

> Si la clé Anthropic a été révoquée entre-temps : en créer une nouvelle sur
> https://console.anthropic.com/ et mettre à jour `local.settings.json` aussi.

### 4.4 Choisir la master data puis déployer le code

⚠️ **État au moment de la sauvegarde : la prod tournait sur la master data de
DÉMO** (22 clients fictifs, codes `90000xx`) — voir `demo/README.md`. La vraie
est dans `cci-function/app/master_data.REEL.backup.xlsx`. Pour une reprise en
**production réelle** :

```bash
cp cci-function/app/master_data.REEL.backup.xlsx cci-function/app/master_data.xlsx
```

Puis déployer :

```bash
cd cci-function
func azure functionapp publish trb-cci-extraction-ae73fa --build remote
```

### 4.5 Récupérer la nouvelle clé d'appel

```bash
KEY=$(az functionapp keys list -n trb-cci-extraction-ae73fa -g trb-cci-rg \
  --query "functionKeys.default" -o tsv)
echo "$KEY"
```

Test de santé (sans clé → **401 attendu** ; 401 = sain, pas une panne) :

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "https://trb-cci-extraction-ae73fa.azurewebsites.net/api/extract"
```

### 4.6 Recréer la connexion API SharePoint

```bash
SUB=$(az account show --query id -o tsv)
az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/trb-cci-rg/providers/Microsoft.Web/connections/sharepointonline?api-version=2016-06-01" \
  --body "{\"location\":\"switzerlandnorth\",\"properties\":{\"displayName\":\"SharePoint TRB\",\"api\":{\"id\":\"/subscriptions/$SUB/providers/Microsoft.Web/locations/switzerlandnorth/managedApis/sharepointonline\"}}}"
```

Puis **étape manuelle obligatoire** (OAuth interactif, impossible en CLI) :
Portail Azure → groupe `trb-cci-rg` → connexion API `sharepointonline` →
**Modifier la connexion API** → **Autoriser** → se connecter avec
`fantin.schellekens@trbchemedica.com` → **Enregistrer**.

### 4.7 Recréer la Logic App

La définition complète est dans `azure-backup/40-logicapp-definition.json`.
Trois choses à remplacer dans le JSON avant de le pousser :

1. l'**ID de souscription** (partout dans `$connections`) ;
2. la **clé de fonction** dans les 3 URL `?code=…` (actions `HTTP`, `HTTP_Build`,
   `HTTP_Build_erreurs`) → remplacer par `$KEY` de l'étape 4.5 ;
3. le **nom de la Function App** dans ces URL, s'il a changé.

Préparation (extrait uniquement `location` + `definition` + `parameters`,
en corrigeant souscription et clé) :

```bash
cd azure-backup
python3 - <<'EOF'
import json, subprocess
sub = subprocess.run(["az","account","show","--query","id","-o","tsv"],
                     capture_output=True, text=True).stdout.strip()
key = "<COLLER ICI LA NOUVELLE CLÉ (étape 4.5)>"
src = json.load(open("40-logicapp-definition.json"))
old_sub = "5e207121-3672-4bd2-a92e-bb03285123d9"
body = {"location": "switzerlandnorth",
        "properties": {"definition": src["properties"]["definition"],
                        "parameters": src["properties"]["parameters"]}}
txt = json.dumps(body)
txt = txt.replace(old_sub, sub)
import re  # remplace toute ancienne clé ?code=… par la nouvelle
txt = re.sub(r"code=[A-Za-z0-9_\-=]+", "code=" + key, txt)
open("logicapp-restore.json","w").write(txt)
print("OK -> logicapp-restore.json")
EOF

az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/trb-cci-rg/providers/Microsoft.Logic/workflows/trb-cci-logic?api-version=2019-05-01" \
  --body @logicapp-restore.json
```

### 4.8 Validation de bout en bout

1. Déposer 1 ou 2 PDF de test dans SharePoint → `Commandes-PDF`
   (des exemples : `demo/commandes_fake/` ou `cci-function/sample_commande.png`).
2. Déclencher la Logic App manuellement :
   ```bash
   az rest --method post \
     --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/trb-cci-rg/providers/Microsoft.Logic/workflows/trb-cci-logic/triggers/Recurrence/run?api-version=2019-05-01"
   ```
3. Vérifier : un `CCI-Lot-*.xlsx` apparaît dans `Uppload-CCI`, les PDF traités
   partent dans `Commandes-Done` (ou `A-revoir` pour les rejets).
4. Historique des exécutions : Portail → `trb-cci-logic` → *Runs history*, ou
   `az rest --method get --url ".../workflows/trb-cci-logic/runs?api-version=2019-05-01"`.

## 5. Points d'attention

- **Le déploiement est manuel** : pousser sur GitHub ne met PAS Azure à jour.
  Toujours `func azure functionapp publish … --build remote` après un changement.
- **Jeton Azure TRB** : l'accès conditionnel TRB limite le refresh token à ~48 h.
  La reconnexion par device code est décrite en 4.1 (et dans la mémoire projet
  `azure-cci-deploy`).
- **`az functionapp show` peut planter localement** (erreur `pyexpat`/dlopen du
  Python Homebrew) — contourner avec `az rest --method get --url
  "…/Microsoft.Web/sites/<app>?api-version=2023-12-01"`.
- Le sélecteur de dossier SharePoint du concepteur Logic App ne charge pas dans
  ce navigateur : la définition se lit/écrit via `az rest` (comme en 4.7). Les
  identifiants de dossiers SharePoint dans la définition sont **relatifs au site
  et doublement encodés** — ne pas y toucher, ils sont déjà corrects dans le JSON.
- Anciennes clés (fonction, stockage) dans `azure-backup/` : **mortes** après la
  résiliation, gardées pour référence. Les nouvelles seront différentes.
- Docs liées : `docs/OVERVIEW.md` (fonctionnement), `cci-function/DEPLOIEMENT.md`
  (ancienne instance), `docs/HANDOFF-logic-app.md` (contexte historique — la
  définition live sauvegardée fait foi en cas d'écart).

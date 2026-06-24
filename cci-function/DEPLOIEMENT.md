# Déploiement Azure — instance en service

Référence de l'instance déployée (mise en service le 2026-06-24).

| | |
|---|---|
| **URL de la fonction** | `https://trb-cci-extraction-ae73fa.azurewebsites.net/api/extract` |
| **Méthode** | `POST` (fichier brut dans le corps) |
| **Function App** | `trb-cci-extraction-ae73fa` |
| **Groupe de ressources** | `trb-cci-rg` |
| **Région** | `switzerlandnorth` (données Azure en Suisse) |
| **Compte de stockage** | `trbccistae73fa` |
| **Runtime** | Python 3.11, Functions v4, plan Consumption (Linux) |
| **Auth** | clé requise (`?code=…` en query, ou en-tête `x-functions-key`) |

> La clé API Anthropic est dans les Application Settings (`ANTHROPIC_API_KEY`),
> chiffrée côté Azure — jamais dans le code ni le dépôt.

## Récupérer la clé d'appel (secret — ne pas committer)

```bash
# Clé d'hôte (recommandée, vaut pour toutes les fonctions de l'app)
az functionapp keys list \
  --name trb-cci-extraction-ae73fa --resource-group trb-cci-rg \
  --query "functionKeys.default" -o tsv
```

Ou via le Portail : Function App → **App keys** → `default`.
(La clé de fonction par fonction est sous Functions → `extract` → *Function keys*.)

## Tester l'URL déployée

```bash
KEY="<colle-ta-clé-ici>"
curl -X POST \
  "https://trb-cci-extraction-ae73fa.azurewebsites.net/api/extract?filename=commande.pdf&code=$KEY" \
  -H "Content-Type: application/pdf" \
  --data-binary @"/chemin/vers/commande.pdf" \
  --output resultat.xlsx
```

## Re-déployer après une modification du code

```bash
cd cci-function
func azure functionapp publish trb-cci-extraction-ae73fa --build remote
```

## Voir les logs en direct

```bash
az webapp log tail \
  --name trb-cci-extraction-ae73fa --resource-group trb-cci-rg
```

## Branchement Power Automate (étape suivante)

Action **HTTP** :
- Méthode : `POST`
- URI : l'URL ci-dessus **avec** `?filename=<nom>&code=<clé>` (ou clé via l'en-tête
  `x-functions-key`)
- En-tête : `Content-Type` selon le fichier (`application/pdf`, `image/png`…)
- Corps : **le contenu binaire de la pièce jointe** (sortie de l'action SharePoint
  « Obtenir le contenu du fichier »)
- La réponse (corps) est le `.xlsx` → à déposer dans le dossier SharePoint de sortie.

# Prompt de reprise — Automatisation CCI (TRB Chemedica)

> Colle tout ce qui suit dans un nouveau chat Claude Code, **dans ce même dépôt**.
> Le nouveau chat aura accès aux fichiers du dépôt mais PAS à l'historique de
> conversation : ce prompt lui redonne tout le contexte.

---

## Qui je suis / contexte
Je suis à **TRB Chemedica (Genève)**, **pas expert Azure**, et je parle français.
On automatise la création de **commandes clients internes (CCI)** dans l'ERP
**ProConcept**. Flux cible :

```
Commandes (PDF) déposées dans un dossier SharePoint
  → traitement par LOT (tous les jours à 15h + lancement manuel)
  → une Azure Function lit chaque doc avec Claude et en extrait les données
  → la fonction génère un Excel CCI (format déterministe, openpyxl)
  → l'Excel est déposé dans un dossier SharePoint de sortie
```

## Ce qui est FAIT et validé (NE PAS refaire)
- **Azure Function Python construite, déployée et validée EN PRODUCTION** : elle
  lit le PDF/image, gère le **manuscrit** (corrections raturées), **croise un
  master data** (client → TVA, monnaie, conditions de paiement, mode d'expédition,
  incoterm…), et génère un **Excel CCI déterministe** (1 ligne/commande).
  - Code : dossier **`cci-function/`** du dépôt.
  - **URL** : `https://trb-cci-extraction-ae73fa.azurewebsites.net/api/extract`
    (POST ; fichier brut dans le corps ; `?filename=<nom>&code=<clé de fonction>`).
  - Ressources Azure : groupe **`trb-cci-rg`**, région **`switzerlandnorth`**,
    app **`trb-cci-extraction-ae73fa`**, stockage **`trbccistae73fa`**.
  - Clé **Anthropic** : dans les *Application Settings* (`ANTHROPIC_API_KEY`),
    modèle `claude-sonnet-4-6`. Jamais dans le code.
  - **Clé d'appel** de la fonction (déjà collée dans l'action HTTP du Logic App) ;
    si besoin la récupérer :
    `az functionapp keys list --name trb-cci-extraction-ae73fa --resource-group trb-cci-rg --query "functionKeys.default" -o tsv`
- **Docs/code dans le dépôt** :
  - `cci-function/README.md` (déploiement + test local)
  - `cci-function/DEPLOIEMENT.md` (instance déployée, contrat HTTP)
  - `docs/superpowers/specs/2026-06-23-cci-azure-function-design.md` (conception)
  - `Donnees_CCI.xlsx` (spec des 22 données CCI, colonne « Source »)
  - `cci-function/app/master_data.xlsx` (master data d'exemple, 3 partenaires)
- **Outils installés (macOS)** : `az` 2.87 (connecté : `fantin.schellekens@trbchemedica.com`,
  abonnement **"Azure subscription 1"** = essai gratuit), `func` 4.12.

## Décision d'architecture (IMPORTANT)
- **Power Automate premium n'est PAS disponible** → l'action HTTP standard de
  Power Automate est impossible (elle est premium).
- On a donc choisi **Azure Logic Apps (Consumption)** pour l'orchestration :
  action HTTP native, pas de licence premium, facturé à l'usage sur l'abonnement
  Azure déjà en place.

## Où on en est — le Logic App
- **Logic App créé** : **`trb-cci-logic`** (groupe `trb-cci-rg`, Switzerland North,
  plan **Consommation**).
- **Déclencheur** : **Récurrence**, tous les jours à **15:00** (fuseau UTC+01
  Bruxelles/Berne). Lancement manuel = bouton **« Exécuter le déclencheur »**.
- **Flux déjà construit dans le concepteur** :
  1. SharePoint **« Lister le dossier »** (dossier d'entrée) ← ⚠️ EN ÉCHEC (voir plus bas)
  2. **Pour chaque** fichier (sortie = **`Corps`** de l'étape 1) :
     a. SharePoint **« Obtenir le contenu du fichier »** (Identificateur = `Identifier`)
     b. **HTTP** POST → URL de la fonction `?filename=<Name>&code=<clé>`,
        en-tête `Content-Type: application/octet-stream`, corps = `Contenu du fichier`
     c. SharePoint **« Créer le fichier »** dans le dossier de sortie
        (Nom = `CCI-` + `Name` + `.xlsx`, Contenu = **`Corps`** de l'action HTTP)

## ⚠️ LE BLOCAGE ACTUEL (à résoudre EN PREMIER)
L'étape **« Lister le dossier »** échoue : **HTTP 400 « Route did not match »**.

- **Cause** : l'**identificateur de dossier** est **tapé à la main**, parce que le
  **sélecteur de dossier 📁 ne charge pas** (très probablement un blocage navigateur :
  pop-ups / cookies tiers). Ce champ attend une valeur générée par le sélecteur ;
  tout chemin tapé échoue.
- **Valeurs déjà essayées (toutes en échec)** :
  - `Smart_Supply/Entrees-de-commandes/Commandes-PDF`
  - `/sites/HQSupply/Smart_Supply/Entrees-de-commandes/Commandes-PDF`
- **Confirmé** : `Smart_Supply` est une **bibliothèque** du site HQSupply (PAS un
  sous-site : la liste déroulante « Adresse du site » ne montre que `HQSupply`).
  Donc **Adresse du site = `HQSupply`** est correcte.
- **Définition JSON de l'action en échec** :
  ```json
  {
    "type": "ApiConnection",
    "inputs": {
      "host": { "connection": { "referenceName": "sharepointonline" } },
      "method": "get",
      "path": "/datasets/@{encodeURIComponent(encodeURIComponent('https://trbchemedica0.sharepoint.com/sites/HQSupply'))}/folders/@{encodeURIComponent('Smart_Supply/Entrees-de-commandes/Commandes-PDF')}"
    },
    "runAfter": {}
  }
  ```

## SharePoint — chemins exacts
- **Site** : `https://trbchemedica0.sharepoint.com/sites/HQSupply`
- **Entrée** (PDF à traiter) : `Smart_Supply/Entrees-de-commandes/Commandes-PDF`
  *(contient 1 PDF de test)*
- **Sortie** (Excel CCI) : `Smart_Supply/Entrees-de-commandes/Uppload-CCI`
- **« Traités »** (archive des originaux) : **pas encore créé** (nécessaire pour ne
  pas retraiter les mêmes fichiers chaque jour à 15h).

## Prochaines étapes (dans l'ordre)
1. **Débloquer « Lister le dossier »** :
   - **Plan A** : faire fonctionner le sélecteur 📁 → ouvrir le portail Azure dans
     **Microsoft Edge**, autoriser pop-ups + cookies tiers pour `portal.azure.com`
     et `sharepoint.com`, rouvrir l'action, vider le champ, recliquer 📁, naviguer
     `Smart_Supply` → `Entrees-de-commandes` → **`Commandes-PDF`** et sélectionner.
   - **Plan B** (si le sélecteur refuse) : remplacer par **« Obtenir les fichiers
     (propriétés uniquement) »** → **Bibliothèque = `Smart_Supply`** (menu déroulant,
     qui fonctionne), puis **filtrer** dans la boucle pour ne garder que les fichiers
     du dossier `Commandes-PDF` (condition sur le chemin). À valider : est-ce que
     cette action remonte bien les fichiers des sous-dossiers ?
2. **Tester** : « Exécuter le déclencheur » → vérifier qu'un `.xlsx` **correct**
   apparaît dans `Uppload-CCI` (l'ouvrir : client, SKU, quantité, TVA…).
   - Point de vigilance : que le **Corps** de l'action HTTP arrive bien en **binaire**
     dans « Créer le fichier » (sinon l'Excel serait corrompu → on ajusterait).
3. **Phase 6** : créer un dossier **« Traités »** et ajouter **« Déplacer le fichier »**
   pour y déplacer l'original **après succès** (sinon retraité chaque jour).
4. **Gestion d'erreurs** : si la fonction renvoie **422** (document illisible) ou une
   autre erreur, router le fichier vers un dossier **« À revoir »** et NE PAS le
   déplacer dans « Traités » ; faire en sorte qu'un fichier en échec ne fasse pas
   échouer tout le lot.
5. (Plus tard) bouton de lancement manuel convivial pour les utilisateurs (flux
   bouton séparé) ; raccourcir le nommage des fichiers de sortie.

## Docs de référence
- **Connecteur SharePoint** (Logic Apps / Power Automate) : Microsoft Learn —
  « SharePoint connector reference » (actions *List folder*, *Get files (properties
  only)*, *Get file content*, *Create file*, *Move file*).
- **Azure Logic Apps (Consumption)** : Microsoft Learn.
- **La fonction et son contrat HTTP** : `cci-function/DEPLOIEMENT.md`.

## Ce que je veux maintenant
Aide-moi, **écran par écran** (je ne suis pas expert Azure), à :
1. débloquer l'étape « Lister le dossier » (Plan A puis Plan B),
2. tester le flux de bout en bout,
3. ajouter le déplacement vers « Traités » et la gestion d'erreurs.
Avance par petites étapes et demande-moi de confirmer chaque étape.

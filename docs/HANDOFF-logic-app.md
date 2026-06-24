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
- **Le Logic App d'orchestration est FONCTIONNEL DE BOUT EN BOUT** (voir
  « Résolution » ci-dessous) : il liste les PDF, appelle la fonction, et dépose
  un **Excel CCI correct** dans le dossier de sortie. Validé le 2026-06-24 avec
  le PDF de test (fichier `CCI-VERIFY.xlsx` contenant les 22 champs CCI + les
  données extraites : RheinCare Solutions GmbH, PO 8362, SKU 462830/462845…).
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

## Le Logic App
- **Logic App** : **`trb-cci-logic`** (groupe `trb-cci-rg`, Switzerland North,
  plan **Consommation**).
- **Déclencheur** : **Récurrence**, tous les jours à **15:00** (fuseau
  « Romance Standard Time » = UTC+01). Lancement manuel = **« Exécuter le déclencheur »**.
- **Astuce technique cruciale** : le **sélecteur de dossier 📁** du concepteur
  SharePoint **ne charge pas** dans ce navigateur. Pour cette raison, le flux a
  été **mis au point et corrigé directement via `az` en CLI** (lecture/écriture
  de la définition du workflow par l'API de management), pas dans le concepteur.
  Commandes utiles :
  - Lire la définition :
    `az resource show -g trb-cci-rg -n trb-cci-logic --resource-type Microsoft.Logic/workflows`
  - Déclencher manuellement (API) :
    `az rest --method post --url ".../workflows/trb-cci-logic/triggers/Recurrence/run?api-version=2019-05-01"`
  - Lire les runs / actions / répétitions : `.../runs`, `.../runs/{id}/actions`,
    `.../runs/{id}/actions/{action}/repetitions`.
- **Flux (5 actions, toutes ✅)** :
  1. SharePoint **« Lister le dossier »** (dossier d'entrée)
  2. **Pour chaque** fichier (sortie = **`Corps`** de l'étape 1) :
     a. SharePoint **« Obtenir le contenu du fichier »**
     b. **HTTP** POST → fonction `?filename=<Name>&code=<clé>`
     c. SharePoint **« Créer le fichier »** dans le dossier de sortie

## ✅ Résolution du blocage (2026-06-24)
Le blocage initial (« Lister le dossier » → **HTTP 400 "Route did not match"**)
était un problème d'**encodage** ET de **format de chemin**, pas le sélecteur 📁.
Trois correctifs ont rendu le flux fonctionnel ; ils sont **déjà déployés** :

1. **Lister le dossier** — l'identificateur doit être **relatif au site** (PAS
   `/sites/HQSupply` devant) ET **doublement encodé** (comme le dataset) :
   ```
   /folders/@{encodeURIComponent(encodeURIComponent('/Smart_Supply/Entrees-de-commandes/Commandes-PDF'))}
   ```
   (Simple encodage → les `/` se re-décodent → "Route did not match". Avec
   `/sites/HQSupply` devant → 404 "Folder not found". La bonne forme est
   `/Smart_Supply/…`. Les noms de dossiers sont **sans accents**.)

2. **Obtenir le contenu du fichier** — utiliser le **chemin complet** `Path` du
   fichier (pas `Name`), lui aussi **doublement encodé** :
   ```
   /files/@{encodeURIComponent(encodeURIComponent(item()?['Path']))}/content
   ```

3. **HTTP → Azure Function** — **retirer le mode de transfert « Chunked »**
   (`runtimeConfiguration.contentTransfer`). Une Azure Function HTTP ne sait pas
   négocier le protocole chunked de Logic Apps → la fonction recevait un corps
   vide (`400 : "Corps de requête vide"`). Sans chunked, les octets bruts passent.

4. **Créer le fichier** — laissé **tel quel** : corps = `@body('HTTP')`, mode
   **Chunked conservé**, `overwrite=true`. ⚠️ Ne PAS « corriger » avec
   `base64ToBinary` : ce n'est pas nécessaire et c'est un faux problème.
   (Piège : la taille affichée du fichier stocké diffère de la sortie fonction —
   c'est un **transcodage/re-compression bénin** du connecteur, PAS une
   corruption. Vérifié : le xlsx s'ouvre et contient les bonnes données.)

Le script de reconstruction déterministe de la définition (depuis une sauvegarde
de l'original + ces 4 réglages) a été utilisé pendant la mise au point.

## SharePoint — chemins exacts
- **Site** : `https://trbchemedica0.sharepoint.com/sites/HQSupply`
- **Entrée** (PDF à traiter) : `/Smart_Supply/Entrees-de-commandes/Commandes-PDF`
  *(identificateur relatif au site ; contient 1 PDF de test)*
- **Sortie** (Excel CCI) : `Smart_Supply/Entrees-de-commandes/Uppload-CCI`
- **« Traités »** (archive des originaux) : **pas encore créé** (nécessaire pour ne
  pas retraiter les mêmes fichiers chaque jour à 15h).
- ⚠️ Le connecteur SharePoint REST n'est pas accessible avec le jeton `az` (401 :
  le tenant n'autorise pas l'app Azure CLI). Toute lecture/écriture SharePoint de
  vérification se fait **via le connecteur du Logic App** (lui est autorisé).

## Prochaines étapes (dans l'ordre)
1. **Nettoyage** : supprimer les fichiers de test dans `Uppload-CCI`
   (`CCI-RAWTEST.xlsx`, `CCI-VERIFY.xlsx`, et l'éventuel
   `CCI-Commande_test_…pdf.xlsx`). À faire à la main dans SharePoint.
2. **Phase 6 — « Traités »** : créer un dossier **« Traités »** et ajouter
   **« Déplacer le fichier »** pour y déplacer l'original **après succès** (sinon
   retraité chaque jour à 15h).
3. **Gestion d'erreurs** : si la fonction renvoie **422** (document illisible) ou
   une autre erreur, router le fichier vers un dossier **« À revoir »** et NE PAS
   le déplacer dans « Traités » ; un fichier en échec ne doit pas faire échouer
   tout le lot (configurer le `runAfter` / la portée).
4. **Nommage de sortie** : actuellement `CCI-<nomPDF>.xlsx` (contient le `.pdf`
   au milieu, moche). La fonction renvoie déjà un nom propre dans son en-tête
   `Content-Disposition` (`CCI-AAAAMMJJ-HHMMSS.xlsx`) — on peut s'en servir, ou
   retirer l'extension d'origine.
5. (Plus tard) bouton de lancement manuel convivial pour les utilisateurs (flux
   bouton séparé).

## Docs de référence
- **Connecteur SharePoint** (Logic Apps / Power Automate) : Microsoft Learn —
  « SharePoint connector reference » (actions *List folder*, *Get files (properties
  only)*, *Get file content*, *Create file*, *Move file*).
- **Azure Logic Apps (Consumption)** : Microsoft Learn.
- **La fonction et son contrat HTTP** : `cci-function/DEPLOIEMENT.md`.

## Ce que je veux maintenant
Aide-moi, **écran par écran** (je ne suis pas expert Azure), à continuer :
1. nettoyer les fichiers de test,
2. ajouter le déplacement vers « Traités » après succès,
3. ajouter la gestion d'erreurs (422 → « À revoir »).
Avance par petites étapes et demande-moi de confirmer chaque étape.

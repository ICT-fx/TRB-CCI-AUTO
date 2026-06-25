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
  → le PDF d'origine est archivé (ou routé vers « à revoir » si illisible)
```

## État global : ✅ PIPELINE COMPLET ET VALIDÉ EN PRODUCTION (2026-06-25)
Tout le flux de bout en bout fonctionne et a été validé avec des fichiers réels.

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
  - **Clé d'appel** de la fonction (déjà dans l'action HTTP du Logic App) ; si
    besoin : `az functionapp keys list --name trb-cci-extraction-ae73fa --resource-group trb-cci-rg --query "functionKeys.default" -o tsv`
  - Réponse : `200` avec l'Excel (binaire) si lisible ; **non-2xx** (ex. 422) si
    illisible / erreur — c'est ce qui déclenche le routage « A-revoir ».
- **Le Logic App `trb-cci-logic` est FONCTIONNEL DE BOUT EN BOUT** (voir détail
  ci-dessous) : liste les PDF, appelle la fonction, dépose l'Excel CCI, archive le
  PDF traité, et route les illisibles vers « A-revoir ». Validé le 2026-06-25.
- **Docs/code dans le dépôt** :
  - `cci-function/README.md`, `cci-function/DEPLOIEMENT.md`
  - `docs/superpowers/specs/2026-06-23-cci-azure-function-design.md`
  - `Donnees_CCI.xlsx` (spec des 22 données CCI), `cci-function/app/master_data.xlsx`
- **Outils (macOS)** : `az` 2.87 (connecté `fantin.schellekens@trbchemedica.com`,
  abonnement "Azure subscription 1"), `func` 4.12.

## Décision d'architecture (IMPORTANT)
- **Power Automate premium PAS disponible** → on utilise **Azure Logic Apps
  (Consumption)** : action HTTP native, pas de licence premium.

## Le Logic App `trb-cci-logic`
- Groupe `trb-cci-rg`, Switzerland North, plan **Consommation**.
- **Déclencheur** : Récurrence tous les jours à **15:00** (« Romance Standard Time »
  = UTC+01). Lancement manuel = **« Exécuter le déclencheur »**.
- **⚠️ Le sélecteur de dossier 📁 du concepteur ne charge pas** dans ce navigateur.
  Tout a donc été **mis au point via `az` en CLI** (lecture/écriture de la
  définition du workflow par l'API de management `Microsoft.Logic/workflows`,
  `api-version=2019-05-01`). Commandes utiles :
  - Lire la def : `az resource show -g trb-cci-rg -n trb-cci-logic --resource-type Microsoft.Logic/workflows`
  - Déclencher : `az rest --method post --url ".../workflows/trb-cci-logic/triggers/Recurrence/run?api-version=2019-05-01"`
  - Runs / actions / répétitions (boucle) : `.../runs`, `.../runs/{id}/actions`,
    `.../runs/{id}/actions/{action}/repetitions`. Les sorties sont dans
    `properties.outputsLink.uri` (à `curl`).
  - Le connecteur **SharePoint REST direct n'est pas accessible** avec le jeton
    `az` (401 ; le tenant n'autorise pas l'app Azure CLI). Toute lecture/écriture
    SharePoint passe par le **connecteur du Logic App**.
- **Flux déployé (`For_each` sur la liste des PDF)** :
  1. `Liste_du_dossier` (List folder) — entrée `Commandes-PDF`
  2. Pour chaque fichier :
     - `Obtenir_le_contenu_du_fichier` (Get file content)
     - `HTTP` POST → fonction
     - `Créer_un_fichier` (Create file) → Excel dans `Uppload-CCI` *(runAfter HTTP=Succeeded)*
     - `Deplacer_vers_Commandes_Done` (Move file) → archive le PDF *(runAfter Créer=Succeeded)*
     - `Deplacer_vers_A_revoir` (Move file) → route le PDF *(runAfter HTTP=Failed/TimedOut)*

## ✅ Détails de mise au point (les pièges résolus)
1. **List folder / Get file content** — identificateurs **relatifs au site**
   (PAS de `/sites/HQSupply` devant) ET **doublement encodés** :
   - `…/folders/@{encodeURIComponent(encodeURIComponent('/Smart_Supply/Entrees-de-commandes/Commandes-PDF'))}`
   - `…/files/@{encodeURIComponent(encodeURIComponent(item()?['Path']))}/content`
   - (Simple encodage → 400 "Route did not match" ; avec `/sites/HQSupply` → 404.)
2. **HTTP → fonction** — **retirer le mode « Chunked »** (`runtimeConfiguration`),
   sinon la fonction reçoit un corps vide (400 "Corps de requête vide").
3. **Créer le fichier** — laissé tel quel : corps `@body('HTTP')`, **Chunked
   conservé**, `overwrite=true`. ⚠️ Ne PAS utiliser `base64ToBinary` (faux
   problème). La différence de taille à l'écriture est un transcodage bénin, PAS
   une corruption (xlsx vérifié : s'ouvre, 22 champs + données correctes).
4. **Move file** (`moveFileAsync`) — corps JSON : `sourceFileId = @item()?['Id']`,
   `destinationDataset` = URL du site, `destinationFolderPath` = chemin relatif au
   site (`/Smart_Supply/Entrees-de-commandes/Commandes-Done` ou `…/A-revoir`),
   `nameConflictBehavior = 2` (renommer si conflit → jamais d'échec/écrasement).
   Le move **ne crée pas** le dossier de destination ; il doit exister.
5. **Création de dossier** : l'op `CreateFolder` (`/folders`) **n'est PAS
   implémentée** par le connecteur (500). Les dossiers ont été **créés à la main
   dans SharePoint** (le sélecteur cassé ne concerne que le concepteur, pas
   SharePoint web).

## SharePoint — chemins exacts
- **Site** : `https://trbchemedica0.sharepoint.com/sites/HQSupply`
- Bibliothèque **Smart_Supply** → dossier **Entrees-de-commandes** contenant :
  - **`Commandes-PDF`** — entrée (PDF à traiter)
  - **`Uppload-CCI`** — sortie (Excel CCI), nom `CCI-<nomPDF>.xlsx`
  - **`Commandes-Done`** — archive des PDF traités avec succès
  - **`A-revoir`** — PDF illisibles / en erreur
- Identifiants pour le connecteur = **relatifs au site**, ex.
  `/Smart_Supply/Entrees-de-commandes/Commandes-PDF`.

## Comportement / points à connaître
- Un lot contenant un fichier illisible apparaît **rouge** dans l'historique des
  runs (l'action HTTP est en échec) — c'est **normal et utile** (« va voir
  `A-revoir` ») ; les autres fichiers du lot sont quand même traités.
- Si l'Excel de sortie est **ouvert dans Excel** au moment du run, l'écrasement
  échoue (« already exists » = verrou) et le PDF n'est pas archivé (retraité au
  run suivant). En production (15h), les sorties ne sont pas ouvertes → OK.
- Claude lit très bien les scans « difficiles » : un PDF « peu lisible » mais
  exploitable est traité normalement ; seuls les fichiers vraiment inexploitables
  partent en `A-revoir`.

## Prochaines étapes (optionnel / polissage)
1. **Nettoyer les fichiers de test** (à la main dans SharePoint) :
   - `A-revoir` : `test-illisible.pdf`
   - `Uppload-CCI` : `CCI-VERIFY.xlsx`, `CCI-RAWTEST.xlsx`, `CCI-MOVETEST.xlsx`
     (et les CCI de test si tu veux repartir propre).
   - Replacer/retirer les PDF de test dans `Commandes-PDF` / `Commandes-Done`
     selon ce que tu veux garder comme jeu d'essai.
   - L'op connecteur **DeleteFile** existe (`DELETE /datasets/{dataset}/files/{id}`)
     si on veut automatiser la suppression.
2. **Nommage de sortie** : actuellement `CCI-<nomPDF>.xlsx` (contient le `.pdf`
   au milieu). La fonction renvoie déjà un nom propre dans `Content-Disposition`
   (`CCI-AAAAMMJJ-HHMMSS.xlsx`) — on peut s'en servir, ou retirer l'extension.
3. (Plus tard) bouton de lancement manuel convivial (flux bouton séparé) ;
   éventuellement distinguer 422 (illisible → A-revoir) des erreurs transitoires
   (laisser en place pour réessai) via une condition sur le code HTTP.

## Docs de référence
- Connecteur SharePoint (Logic Apps) : Microsoft Learn « SharePoint connector
  reference ». La **swagger** du connecteur s'exporte via
  `az rest --method get --url ".../managedApis/sharepointonline?api-version=2018-07-01-preview&export=true"`.
- La fonction et son contrat HTTP : `cci-function/DEPLOIEMENT.md`.

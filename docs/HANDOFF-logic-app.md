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
Commandes (PDF/images) déposées dans un dossier SharePoint
  → traitement par LOT (tous les jours à 15h + lancement manuel)
  → une Azure Function lit chaque doc avec Claude et en extrait les données
  → les commandes lisibles sont consolidées dans UN SEUL Excel CCI (1 ligne/commande)
  → l'Excel est déposé dans un dossier SharePoint de sortie
  → le PDF d'origine est archivé ; les illisibles/incomplets vont en « A-revoir »
```

## État global : ✅ COMPLET ET VALIDÉ EN PRODUCTION (2026-06-26)
Les 3 exigences récentes sont livrées et validées de bout en bout :
1. **SKU = code à 4 chiffres** imposé (l'IA ne prend plus un code à 6 chiffres ni un
   n° d'article client).
2. **Documents illisibles/incomplets → `A-revoir`** (HTTP 422), au lieu de produire
   un Excel faux.
3. **Un seul Excel consolidé par lot**, **1 ligne = 1 commande**.

## Ce qui est FAIT et validé (NE PAS refaire)
- **Azure Function Python** (`cci-function/`), déployée sur **`trb-cci-extraction-ae73fa`**
  (groupe `trb-cci-rg`, `switzerlandnorth`, stockage `trbccistae73fa`, Python 3.11
  Functions v4 Consumption). Clé Anthropic dans App Settings (`ANTHROPIC_API_KEY`,
  modèle `claude-sonnet-4-6`). Redéploiement : `cd cci-function && func azure
  functionapp publish trb-cci-extraction-ae73fa --build remote --python`.
  - **Deux routes** (auth FUNCTION ; même clé d'hôte `?code=…`) :
    - **`POST /api/extract`** — 1 document (corps brut) + `?filename=`. Renvoie un
      **record JSON (200)** si la commande est valide, **422** si à rejeter
      (illisible / champ commande manquant / SKU non conforme). Forme du record :
      `{customer_name, partner_reference, requested_delivery_date, incoterm_location,
      destination, products:[{sku,quantity,value}], master:{…,matched,status},
      filename, confidence, quality_note}`.
    - **`POST /api/build`** — `{"rows":[<record>,…]}` → **un Excel consolidé**
      (1 feuille `CCI`, 1 ligne/record, colonnes produits `SKU i/Quantité i/Valeur i`
      jusqu'au max du lot, + diagnostics). **Cellules master vides surlignées jaune.**
- **Logic App `trb-cci-logic`** (Consumption) — orchestration **v2** :
  1. `Initialiser_lignes` (variable tableau `lignes`)
  2. `Liste_du_dossier` (entrée `Commandes-PDF`)
  3. `For_each` **séquentiel** (`concurrency=1`) : `Obtenir_le_contenu_du_fichier`
     → `HTTP` POST `/api/extract` → **si 200** : `Ajouter_ligne` (append à `lignes`)
     + `Deplacer_vers_Commandes_Done` ; **si 422** : `Deplacer_vers_A_revoir`
  4. `Condition_lignes` : si `length(lignes) > 0` → `HTTP_Build` POST `/api/build`
     → `Creer_fichier_consolide` = `CCI-Lot-AAAAMMJJ-HHMMSS.xlsx` dans `Uppload-CCI`
- **Mise au point via `az` CLI** (le sélecteur de dossier 📁 du concepteur ne charge
  pas dans ce navigateur). Lire/écrire la définition :
  `az resource show -g trb-cci-rg -n trb-cci-logic --resource-type Microsoft.Logic/workflows`
  puis `az rest --method put …?api-version=2019-05-01`. Déclencher :
  `az rest --method post .../triggers/Recurrence/run?api-version=2019-05-01`.

## Règles métier (validées)
- **Champs « commande » OBLIGATOIRES** (manquant ⇒ 422 → A-revoir) :
  `customer_name`, `partner_reference`, `requested_delivery_date`, `destination`,
  et **≥ 1 produit valide** (SKU **4 chiffres** + quantité > 0 + valeur ≥ 0).
- **`incoterm_location` (« Lieu de l'incoterm ») est OPTIONNEL** : les commandes
  réelles ne le portent pas (le rendre obligatoire rejetait tout).
- **SKU = code numérique à 4 chiffres.** Un **n° d'article CLIENT** (même à 4
  chiffres) **n'est PAS** un SKU TRB → l'IA renvoie `null` → A-revoir. Une réf
  produit à 6 chiffres n'est pas un SKU non plus.
- **Client hors master data** : la commande est **conservée** (pas A-revoir) ; les
  champs master (TVA, monnaie, incoterm, mode d'expédition…) sont **vides et
  surlignés jaune** dans l'Excel (signal « à compléter »).

## SharePoint — chemins exacts
- Site `https://trbchemedica0.sharepoint.com/sites/HQSupply`, bibliothèque
  **Smart_Supply** → dossier **Entrees-de-commandes** contenant :
  - **`Commandes-PDF`** (entrée) · **`Uppload-CCI`** (sortie : `CCI-Lot-*.xlsx`)
  - **`Commandes-Done`** (archive des PDF traités) · **`A-revoir`** (rejetés)
- Identifiants connecteur = **relatifs au site** + **doublement encodés**
  (ex. `/folders/@{encodeURIComponent(encodeURIComponent('/Smart_Supply/…'))}`).
- Le connecteur SharePoint REST direct n'est pas accessible au jeton `az` (401) :
  tout passe par le **connecteur du Logic App**. `moveFileAsync` : corps JSON avec
  `sourceFileId=@item()?['Id']`, `nameConflictBehavior=2`. `CreateFolder` (`/folders`)
  n'est PAS implémenté → créer les dossiers à la main dans SharePoint.

## À FAIRE par l'utilisateur (hors code)
- **Peupler `cci-function/app/master_data.xlsx`** avec les vrais clients (sinon
  cases jaunes TVA/monnaie/incoterm…). Colonnes : `nom_client, numero_tva, monnaie,
  conditions_paiement_jours, assurance, mode_expedition, incoterm, lieu_provenance,
  destination_edi`. (Re-déployer la fonction après modif du fichier.)

## Roadmap / évolutions connues
- **Catalogue produits** : mapper une **réf produit (6 chiffres)** ou un **n°
  d'article client** vers le **SKU TRB (4 chiffres)**. Tant que ça n'existe pas, les
  commandes sans SKU TRB lisible (ex. ALPINE MEDICA, réf `352740` + article client
  `2600`) partent légitimement en `A-revoir`.
- Nommage horodaté en UTC (`CCI-Lot-AAAAMMJJ-HHMMSS`) ; passer en heure locale si voulu.
- Boucle `For_each` séquentielle (collecte sûre de la variable) : OK pour le volume
  quotidien ; à optimiser si beaucoup de commandes.
- Possible : distinguer 422 « illisible » d'une erreur transitoire (réessai) via le
  code HTTP.

## Spec de conception
- `docs/superpowers/specs/2026-06-26-cci-batch-consolidation-design.md` (ces 3 changements).
- `docs/superpowers/specs/2026-06-23-cci-azure-function-design.md` (fonction initiale).
- `cci-function/DEPLOIEMENT.md` (contrat HTTP, redéploiement, logs).

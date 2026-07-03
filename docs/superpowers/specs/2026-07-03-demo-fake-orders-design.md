# Design — Jeu de démo : commandes truquées + master data de substitution

> Date : 2026-07-03. Objectif : disposer d'un lot de **commandes clients truquées**
> (noms clients fictifs, prix délirants, quantités 1–30, **vrais noms de produits**)
> et d'une **master data de substitution cohérente** pour faire tourner une démo du
> pipeline CCI sans exposer de données réelles.

## But

À partir des 25 PDF de `Commandesafalsifier/`, produire :
1. 25 PDF **truqués** qui reprennent la **structure** de l'original (mêmes blocs, même flux) ;
2. une master data (`clients` + `catalogue`) **cohérente** avec ces commandes, de sorte
   que ~20 se résolvent (record 200) et **~5 partent en « À-revoir » (422)**.

La vraie master data est sauvegardée dans `cci-function/app/master_data.REEL.backup.xlsx`
avant toute substitution.

## Principe directeur

Une **source de vérité unique** (`demo/faked_orders.json`) décrit chaque commande.
Deux scripts en dérivent respectivement les PDF et la master data. Comme les deux
sont générés depuis la même source, la cohérence data↔PDF — et donc le résultat
pass/fail de la démo — est **garantie par construction**.

## Composants

### 1. `demo/faked_orders.json` (source de vérité)
Une entrée par PDF source :
- `source` : nom du fichier original
- `skin` : variante visuelle (ex. `sap`, `invoice-eu`, `letter`)
- `client_name` : raison sociale **fictive** (plausible, cohérente avec le pays de l'original)
- `customer_code` : **7 chiffres**, plage neuve `90xxxxx` (ne croise pas les vrais codes)
- `partner_reference`, `order_date`, `requested_delivery_date`, `currency`
- `sender` / `recipient` : blocs d'adresse (émetteur = client fictif ; destinataire = **TRB, réel**)
- `meta[]` : paires clé/valeur du bandeau PO propres au document
- `columns` : configuration des colonnes du tableau de lignes
- `lines[]` : `{designation (vrai produit TRB), sku (4 chiffres), qty (1–30), unit_price (délirant)}`
- `notes` : bloc pied/mentions
- `outcome` : `pass` | `fail_client` | `fail_product`
- pour `fail_product` : `intruder_line_index` (la ligne hors catalogue)

### 2. `demo/render_orders.py`
Pour chaque entrée : compose un HTML paramétré (blocs émetteur/destinataire, bandeau
méta, tableau de lignes à colonnes configurables, totaux, notes) selon le `skin`, puis
rend en PDF via **Chrome headless** (`--headless --print-to-pdf --no-pdf-header-footer`).
Sortie : `demo/commandes_fake/<nom>.pdf`.

### 3. `demo/build_demo_master_data.py`
Depuis le JSON, écrit `cci-function/app/master_data.xlsx` :
- `clients` = tous les clients **sauf** les `fail_client`
- `catalogue` = par client, les produits de sa commande — **sauf** la ligne intrus des
  `fail_product`
- Les couples **(sku, designation)** sont repris des **vraies paires** du backup, pour
  rester réalistes et cohérents.
Le script **asserte les invariants** (voir Garantie) et échoue si une commande `pass`
n'est pas entièrement couverte, ou si une omission de `fail` n'est pas en place.

### 4. `demo/README.md`
Tableau de contrôle : par document → client fictif, code, **résultat attendu** (pass /
422 + motif), produits.

## Les 5 échecs (à-revoir)

- **3 × `fail_client`** : nom client absent de `clients`, choisi **très distinct** (aucun
  quasi-homonyme dans la master data) pour éviter un rattachement flou par l'IA →
  422 « client introuvable ».
- **2 × `fail_product`** : client présent, mais une ligne = produit **hors de son
  catalogue** → 422 « produit hors catalogue ».

## Réel vs truqué

| Réel (gardé) | Truqué |
|---|---|
| Blocs/adresses TRB Chemedica ; noms de produits ; couples SKU↔désignation | Nom + code client, réf. PO, dates, **quantités (1–30)**, **prix (délirants)** |

Les prix n'étant pas lus par l'outil, les « prix délirants » servent à l'anonymisation /
au réalisme visuel, sans effet sur la résolution.

## Garantie (invariants vérifiés au build)

- Toute commande `pass` ⇒ `client_name` ∈ `clients` **et** chaque `(customer_code, sku,
  designation)` ∈ `catalogue`.
- Toute `fail_client` ⇒ `client_name` ∉ `clients`.
- Toute `fail_product` ⇒ la ligne intrus ∉ catalogue du client (les autres lignes y sont).
- `customer_code` unique par client ; SKU à 4 chiffres ; code à 7 chiffres.

Le vrai pipeline passe par Claude (match flou du nom + correction SKU par désignation) ;
il n'est pas rejouable hors-ligne, mais la cohérence stricte data↔PDF rend le résultat
attendu déterministe.

## Sorties

- `demo/commandes_fake/*.pdf` (25 commandes truquées)
- `cci-function/app/master_data.xlsx` (master data de substitution)
- `cci-function/app/master_data.REEL.backup.xlsx` (vraie master data, préservée)
- `demo/faked_orders.json`, `demo/render_orders.py`, `demo/build_demo_master_data.py`, `demo/README.md`

## Hors périmètre (YAGNI)

- Pas de reproduction pixel-perfect (polices/logos propriétaires) : fidélité **structurelle**.
- Pas de rejeu du pipeline Claude en local ; la garantie repose sur les invariants de build.
- Pas de commandes « illisibles » volontaires (dégraderait le réalisme sans valeur ajoutée).

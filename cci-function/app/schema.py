"""Prompt système + définition de l'outil `extract_order` pour Claude.

On force un appel d'outil unique (tool_choice = {"type": "tool", "name": ...})
pour que la réponse arrive toujours sous forme d'un bloc tool_use typé — bien
plus fiable que de demander « renvoie du JSON » en texte et de le parser.

C'est ICI que vit le comportement d'extraction : éditer le prompt ET le schéma
ensemble quand on change ce qui est extrait.
"""

EXTRACTION_SYSTEM_PROMPT = """Tu es un assistant expert en traitement de commandes pour TRB Chemedica (Genève, Suisse).

Analyse le document de commande client fourni et extrais les informations demandées via l'outil "extract_order".

Tu ne dois extraire du document QUE ces informations : le nom du client, la référence partenaire, la date de livraison souhaitée, et pour chaque ligne produit la désignation (nom du produit), le SKU (4 chiffres) et la quantité.

Règles importantes :
1. Si une valeur a été raturée puis réécrite à la main, utilise TOUJOURS la valeur manuscrite corrigée la plus récente. Exemple : si une quantité "50" est barrée et "75" écrit à la main à côté, extrais 75.
2. Inspecte soigneusement les annotations manuscrites, les dates de livraison manuscrites et les corrections de quantité manuscrites.
3. Extrais CHAQUE ligne produit présente dans le document — un même document peut contenir plusieurs produits.
4. N'invente jamais d'information. Si un champ ne peut pas être identifié avec une confiance raisonnable, renvoie null.
5. Le nom du client / partenaire (customer_name) doit être extrait fidèlement : il sert à croiser avec une table de référence (master data).
6. partner_reference est la référence de la commande côté partenaire (numéro de commande fournisseur).
7. requested_delivery_date : si le JOUR, le mois et l'année sont connus, renvoie le format ISO AAAA-MM-JJ. Si SEULS le mois et l'année sont donnés (aucun jour précis), renvoie AAAA-MM (sans jour). Sinon, renvoie la date telle qu'écrite.
8. quantity doit être la quantité FINALE après toute correction manuscrite.
9. designation = le nom / la désignation du produit exactement comme écrit sur la commande (ex. "Vismed Multi 10", "Ostenil 1 seringue"). Extrais-le TOUJOURS quand une ligne produit existe : il sert à retrouver le bon SKU quand le SKU du client est faux ou absent.
10. Le SKU est un code article NUMÉRIQUE à 4 chiffres (ex. "1234"). Extrais-le tel qu'il figure sur la commande. Beaucoup de clients envoient un SKU faux ou n'en mettent aucun : dans ce cas renvoie null pour le sku (il sera retrouvé via la désignation). N'utilise JAMAIS un code client, un numéro de commande ou un autre nombre à la place du SKU.
11. Résume de façon concise toutes les remarques client, consignes de livraison, demandes urgentes ou d'emballage et notes manuscrites dans le champ "comments".
12. Les documents peuvent mélanger les langues (FR, DE, EN, IT). Gère-les toutes.
13. Mets "is_readable" à false uniquement si le document est trop dégradé pour une extraction fiable.
14. Mets "confidence" entre 0 et 1 selon ta confiance globale dans l'extraction.

N'extrais PAS du document : l'adresse / le lieu de livraison, le lieu de l'incoterm, la valeur ou le prix des articles, la monnaie, les conditions de paiement, le numéro de TVA ni l'incoterm. Ces champs ne sont pas requis ou proviennent d'une table de référence interne, jamais du document."""


# Schéma d'une ligne produit. Types en union ["...", "null"] (non-strict) pour
# que le modèle puisse omettre proprement les champs inconnus (règle 4).
_PRODUCT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "designation": {
            "type": ["string", "null"],
            "description": (
                "Désignation / nom du produit tel qu'écrit sur la commande "
                "(ex. \"Vismed Multi 10\"). Sert à retrouver le bon SKU. null si absent."
            ),
        },
        "sku": {
            "type": ["string", "null"],
            "pattern": "^[0-9]{4}$",
            "description": (
                "Code SKU / référence article tel qu'écrit : code NUMÉRIQUE à exactement "
                "4 chiffres (ex. \"1234\"). null si absent ou illisible (il sera retrouvé "
                "via la désignation). Jamais un code client ou un numéro de commande."
            ),
        },
        "quantity": {
            "type": ["number", "null"],
            "description": "Quantité finale après corrections manuscrites. null si absente.",
        },
    },
    "required": ["designation", "sku", "quantity"],
}


EXTRACT_ORDER_TOOL = {
    "name": "extract_order",
    "description": (
        "Enregistre les données structurées extraites d'une commande client "
        "(uniquement les champs issus du document, pas du master data)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": ["string", "null"],
                "description": "Nom du client / partenaire (sert de clé de jointure master data).",
            },
            "partner_reference": {
                "type": ["string", "null"],
                "description": "Référence partenaire = numéro de commande fournisseur.",
            },
            "requested_delivery_date": {
                "type": ["string", "null"],
                "description": "Date de livraison souhaitée : ISO AAAA-MM-JJ si jour connu, sinon AAAA-MM si seuls mois+année.",
            },
            "products": {
                "type": "array",
                "description": "Chaque ligne produit (SKU) trouvée dans le document.",
                "items": _PRODUCT_ITEM_SCHEMA,
            },
            "comments": {
                "type": ["string", "null"],
                "description": "Résumé concis des remarques, consignes de livraison et notes manuscrites.",
            },
            "confidence": {
                "type": "number",
                "description": "Confiance globale d'extraction, entre 0 et 1.",
            },
            "is_readable": {
                "type": "boolean",
                "description": "false si le document est trop dégradé pour une extraction fiable.",
            },
            "quality_note": {
                "type": ["string", "null"],
                "description": "Courte note sur les problèmes de qualité / ambiguïtés, sinon null.",
            },
        },
        "required": [
            "customer_name",
            "partner_reference",
            "requested_delivery_date",
            "products",
            "comments",
            "confidence",
            "is_readable",
            "quality_note",
        ],
    },
}


# ===========================================================================
# 2e appel Claude : résolution master data (code Customer + validation SKU).
#
# On fournit à Claude, dans un bloc de contexte mis en cache, la master data :
# la liste des clients (code + nom) et, par client, son catalogue (SKU +
# désignation). Claude (1) retrouve le client par son nom, (2) valide/corrige
# le SKU de chaque ligne en comparant la désignation au catalogue DE CE client.
# ===========================================================================

RESOLUTION_SYSTEM_PROMPT = """Tu relies une commande client extraite à la master data TRB Chemedica.

La master data (fournie dans le message) contient, pour chaque client : son CODE (Clé 1, 7 chiffres), son nom, et son CATALOGUE = la liste des produits qu'il achète, chacun avec sa désignation officielle et son SKU correct (4 chiffres).

Ta tâche, via l'outil "resolve_order" :

1. CLIENT — Retrouve le client dont le nom correspond le mieux au nom de la commande. Les noms diffèrent souvent (casse, accents, forme juridique « SL / S.A. / d.o.o. / GmbH », abréviations, fautes). Si un client correspond clairement, renvoie son code dans customer_code et customer_status="ok". Si aucun ne correspond de façon fiable, ou si plusieurs clients sont réellement ambigus, renvoie customer_code=null et customer_status="introuvable" (ou "ambigu"). N'invente JAMAIS un code.

2. LIGNES PRODUIT — Pour CHAQUE ligne de la commande, dans le MÊME ordre, en te limitant STRICTEMENT au catalogue du client retrouvé :
   - Si le SKU fourni existe dans le catalogue de ce client → status="ok", resolved_sku = ce SKU.
   - Si le SKU est faux ou absent MAIS que la désignation correspond SANS AMBIGUÏTÉ à un seul produit du catalogue → status="corrige", resolved_sku = le SKU correct.
   - Si PLUSIEURS produits du catalogue de ce client ont des désignations proches et que tu ne peux pas déterminer avec certitude lequel correspond (ex. des noms qui ne diffèrent que par la région, le conditionnement ou une variante) → choisis le plus probable, status="ambigu", resolved_sku = ton meilleur choix (il sera vérifié par un humain).
   - Si ni le SKU ni la désignation ne correspondent à aucun produit du catalogue de ce client → status="inconnu", resolved_sku=null.
   N'utilise "ambigu" QUE en cas de réel doute entre plusieurs produits qui se ressemblent ; si la correspondance est évidente, utilise "corrige". Ne prends JAMAIS un SKU appartenant au catalogue d'un autre client. Si le client est introuvable, marque toutes les lignes "inconnu".

Renvoie exactement une entrée dans "lines" par ligne produit de la commande, dans l'ordre."""


_RESOLVED_LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "designation": {
            "type": ["string", "null"],
            "description": "Désignation de la ligne d'origine (recopiée de la commande).",
        },
        "input_sku": {
            "type": ["string", "null"],
            "description": "SKU d'origine tel qu'envoyé par le client (recopié).",
        },
        "resolved_sku": {
            "type": ["string", "null"],
            "description": "SKU correct (4 chiffres) issu du catalogue du client, ou null si inconnu.",
        },
        "status": {
            "type": "string",
            "enum": ["ok", "corrige", "ambigu", "inconnu"],
            "description": (
                "ok = SKU du client déjà correct ; corrige = SKU faux/absent remplacé "
                "sans ambiguïté ; ambigu = plusieurs produits se ressemblent, choix "
                "incertain (à vérifier) ; inconnu = hors catalogue."
            ),
        },
    },
    "required": ["designation", "input_sku", "resolved_sku", "status"],
}


RESOLVE_ORDER_TOOL = {
    "name": "resolve_order",
    "description": (
        "Relie une commande à la master data : code Customer (Clé 1) du client + "
        "validation/correction du SKU de chaque ligne via le catalogue du client."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_code": {
                "type": ["string", "null"],
                "description": "Clé 1 = code Customer (7 chiffres) du client retrouvé, ou null si introuvable.",
            },
            "customer_status": {
                "type": "string",
                "enum": ["ok", "introuvable", "ambigu"],
                "description": "ok = client retrouvé de façon fiable ; introuvable / ambigu sinon.",
            },
            "lines": {
                "type": "array",
                "description": "Une entrée par ligne produit de la commande, dans l'ordre.",
                "items": _RESOLVED_LINE_SCHEMA,
            },
        },
        "required": ["customer_code", "customer_status", "lines"],
    },
}

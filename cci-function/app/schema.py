"""Prompt système + définition de l'outil `extract_order` pour Claude.

On force un appel d'outil unique (tool_choice = {"type": "tool", "name": ...})
pour que la réponse arrive toujours sous forme d'un bloc tool_use typé — bien
plus fiable que de demander « renvoie du JSON » en texte et de le parser.

C'est ICI que vit le comportement d'extraction : éditer le prompt ET le schéma
ensemble quand on change ce qui est extrait.
"""

EXTRACTION_SYSTEM_PROMPT = """Tu es un assistant expert en traitement de commandes pour TRB Chemedica (Genève, Suisse).

Analyse le document de commande client fourni et extrais toutes les informations disponibles via l'outil "extract_order".

Règles importantes :
1. Si une valeur a été raturée puis réécrite à la main, utilise TOUJOURS la valeur manuscrite corrigée la plus récente. Exemple : si une quantité "50" est barrée et "75" écrit à la main à côté, extrais 75.
2. Inspecte soigneusement les annotations manuscrites, les dates de livraison manuscrites et les corrections de quantité manuscrites.
3. Extrais CHAQUE ligne produit présente dans le document — un même document peut contenir plusieurs produits.
4. N'invente jamais d'information. Si un champ ne peut pas être identifié avec une confiance raisonnable, renvoie null.
5. Le nom du client / partenaire (customer_name) doit être extrait fidèlement : il sert à croiser avec une table de référence (master data).
6. partner_reference est la référence de la commande côté partenaire (numéro de commande fournisseur).
7. requested_delivery_date : renvoie au format ISO AAAA-MM-JJ si la date est sans ambiguïté ; sinon, renvoie la date telle qu'écrite.
8. quantity doit être la quantité FINALE après toute correction manuscrite.
9. La valeur du SKU (value) peut être 0 : c'est un cas valide, renvoie 0 et non null si une valeur nulle est explicitement indiquée.
10. incoterm_location est le lieu associé à l'incoterm (ex. ville / port), s'il figure sur le document.
11. destination est l'adresse / le lieu de livraison.
12. Résume de façon concise toutes les remarques client, consignes de livraison, demandes urgentes ou d'emballage et notes manuscrites dans le champ "comments".
13. Les documents peuvent mélanger les langues (FR, DE, EN, IT). Gère-les toutes.
14. Mets "is_readable" à false uniquement si le document est trop dégradé pour une extraction fiable.
15. Mets "confidence" entre 0 et 1 selon ta confiance globale dans l'extraction.

Ne renvoie PAS la monnaie, les conditions de paiement, le numéro de TVA ou l'incoterm : ces champs proviennent d'une table de référence interne, pas du document."""


# Schéma d'une ligne produit. Types en union ["...", "null"] (non-strict) pour
# que le modèle puisse omettre proprement les champs inconnus (règle 4).
_PRODUCT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "sku": {
            "type": ["string", "null"],
            "description": "Code SKU / référence article. null si absent.",
        },
        "quantity": {
            "type": ["number", "null"],
            "description": "Quantité finale après corrections manuscrites. null si absente.",
        },
        "value": {
            "type": ["number", "null"],
            "description": "Valeur / prix du SKU (>= 0). 0 est une valeur valide. null si absente.",
        },
    },
    "required": ["sku", "quantity", "value"],
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
                "description": "Date de livraison souhaitée (ISO AAAA-MM-JJ si non ambiguë).",
            },
            "incoterm_location": {
                "type": ["string", "null"],
                "description": "Lieu associé à l'incoterm (ville / port), si présent.",
            },
            "destination": {
                "type": ["string", "null"],
                "description": "Adresse / lieu de livraison.",
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
            "incoterm_location",
            "destination",
            "products",
            "comments",
            "confidence",
            "is_readable",
            "quality_note",
        ],
    },
}

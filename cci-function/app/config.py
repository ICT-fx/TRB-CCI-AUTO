"""Constantes centralisées de la fonction.

Tout ce qui pourrait changer (modèle, constantes de gabarit, ordre des colonnes)
est regroupé ici pour éviter de le disperser dans le code.
"""

import os

# --- Claude --------------------------------------------------------------
# Modèle par défaut : le dernier Claude Sonnet. Surchargable par variable
# d'environnement sans toucher au code (voir CLAUDE.md du projet).
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 8000

# --- Constantes de gabarit de document (CCI ProConcept) ------------------
# Ces deux valeurs sont des constantes (Source = Master Data dans la spec,
# mais identiques pour toutes les CCI au format actuel).
DOCUMENT_TYPE = "Commande Client"
DOCUMENT_TEMPLATE_DESCRIPTION = "Vente - Commande Client"

# Seuil de confiance en-dessous duquel on considère l'extraction douteuse.
# (Le rejet dur se fait sur is_readable ; ce seuil sert au champ "statut".)
LOW_CONFIDENCE_THRESHOLD = 0.5

# -*- coding: utf-8 -*-
"""Flowchart 'Cycle de vie d'une commande — Outil CCI' (style TRB).

Couleurs différenciantes : vert = début/fin, BLEU = automatique (l'outil),
ORANGE = humain (gestionnaire), jaune = décision. Swimlanes ①②③.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
from matplotlib.lines import Line2D

# --- Palette (reprise du style de la collègue) ---------------------------
GREEN_F, GREEN_E = "#E2EFD9", "#548235"      # début / fin
BLUE_F,  BLUE_E  = "#DAE3F3", "#2E4C7E"      # automatique (outil)
ORANGE_F, ORANGE_E = "#FCE4D6", "#C55A11"    # humain (gestionnaire)
YELLOW_F, YELLOW_E = "#FFF2CC", "#BF9000"    # décision
GREY_F, GREY_E   = "#EDEDED", "#808080"      # écarté
TRB_BLUE = "#15578F"
LANE1 = "#EAF1FB"   # ① réception & tri
LANE2 = "#F0ECF7"   # ② traitement auto
LANE3 = "#EBF3E6"   # ③ vérification humaine

W, H = 13.0, 20.4
fig, ax = plt.subplots(figsize=(W, H), dpi=150)
ax.set_xlim(0, 100)
ax.set_ylim(0, 158)
ax.axis("off")

CX = 45          # centre X de la colonne principale
BW, BH = 46, 7   # largeur/hauteur boîte standard


def box(y, text, fill, edge, *, x=CX, w=BW, h=BH, bold=False, fontsize=11,
        style="round", tcolor="#1a1a1a"):
    boxstyle = "round,pad=0.1,rounding_size=1.4" if style == "round" else \
               "round,pad=0.1,rounding_size=3.4"
    p = FancyBboxPatch((x - w/2, y - h/2), w, h, boxstyle=boxstyle,
                       linewidth=1.8, edgecolor=edge, facecolor=fill, zorder=3)
    ax.add_patch(p)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color=tcolor, weight="bold" if bold else "normal", zorder=4,
            wrap=True)
    return y


def diamond(y, text, *, x=CX, w=30, h=11):
    pts = [(x, y + h/2), (x + w/2, y), (x, y - h/2), (x - w/2, y)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=YELLOW_F,
                         edgecolor=YELLOW_E, linewidth=1.8, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=10.5,
            color="#1a1a1a", weight="bold", zorder=4)
    return y


def arrow(y1, y2, *, x=CX, x2=None):
    x2 = x if x2 is None else x2
    ax.add_patch(FancyArrowPatch((x, y1), (x2, y2), arrowstyle="-|>",
                 mutation_scale=18, linewidth=1.7, color="#3a3a3a", zorder=2))


def elbow(x1, y1, x2, y2, color="#C55A11"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                 mutation_scale=16, linewidth=1.7, color=color,
                 connectionstyle="arc3,rad=0", zorder=2))


def lane(y_top, y_bot, color, label, num):
    ax.add_patch(FancyBboxPatch((14, y_bot), 68, y_top - y_bot,
                 boxstyle="round,pad=0.2,rounding_size=1.2", linewidth=0,
                 facecolor=color, zorder=0))
    ax.text(11.5, (y_top + y_bot)/2, f"{num}  {label}", rotation=90,
            ha="center", va="center", fontsize=12.5, weight="bold",
            color=TRB_BLUE, zorder=1)


# ===== Titre ==============================================================
ax.text(50, 156, "Cycle de vie d'une commande — Outil CCI",
        ha="center", va="center", fontsize=20, weight="bold", color=TRB_BLUE)
ax.text(50, 152.4, "Extraction automatique des commandes clients et pré-saisie ProConcept",
        ha="center", va="center", fontsize=11.5, style="italic", color="#555555")

# ===== Légende ============================================================
leg = [
    ("Début / fin", GREEN_F, GREEN_E),
    ("Automatique — l'outil", BLUE_F, BLUE_E),
    ("Humain — gestionnaire", ORANGE_F, ORANGE_E),
    ("Décision", YELLOW_F, YELLOW_E),
]
lx = 12
for name, f, e in leg:
    ax.add_patch(FancyBboxPatch((lx, 147.5), 2.4, 2.4,
                 boxstyle="round,pad=0.05,rounding_size=0.5",
                 linewidth=1.6, edgecolor=e, facecolor=f, zorder=3))
    ax.text(lx + 3.0, 148.7, name, ha="left", va="center", fontsize=9.6,
            color="#333333")
    lx += 3.2 + len(name) * 0.92

# ===== Swimlanes (fonds) ==================================================
lane(145.0, 118.5, LANE1, "RÉCEPTION & TRI", "①")
lane(118.0, 34.5,  LANE2, "TRAITEMENT AUTOMATIQUE — l'outil", "②")
lane(34.0, 8.0,    LANE3, "VÉRIFICATION & SAISIE ProConcept — l'humain", "③")

# ===== ① RÉCEPTION & TRI ==================================================
box(142, "Commande reçue par e-mail", GREEN_F, GREEN_E, bold=True, style="stadium")
arrow(138.5, 135)
box(131.5, "Règle de messagerie : dépôt automatique des pièces jointes\nde certains expéditeurs connus",
    BLUE_F, BLUE_E)
arrow(128, 124.5)
box(121, "Tri humain — le gestionnaire vérifie et dépose chaque commande\ndans le dossier « Commandes-PDF »",
    ORANGE_F, ORANGE_E, bold=True)
# note latérale sur la limite de l'automatisation
ax.add_patch(FancyBboxPatch((70, 118.0), 27, 6.6,
             boxstyle="round,pad=0.2,rounding_size=1.0", linewidth=1.4,
             edgecolor=ORANGE_E, facecolor="#FFF6F0", linestyle=(0,(4,2)), zorder=3))
ax.text(83.5, 121.3, "L'automatisation ne capte pas\ntout → le contrôle humain reste\nindispensable à cette étape",
        ha="center", va="center", fontsize=8.6, color=ORANGE_E)
elbow(70, 121, 68.5, 121, color=ORANGE_E)

# ===== ② TRAITEMENT AUTOMATIQUE ==========================================
arrow(117.5, 114)
box(110.5, "Déclenchement du lot — chaque jour à 15 h (et lancement manuel)",
    GREEN_F, GREEN_E, bold=True, style="stadium")
arrow(107, 103.5)
box(99.5, "1.  Lecture de chaque document par l'IA\nclient · référence · date de livraison · produits (désignation / SKU / quantité)",
    BLUE_F, BLUE_E, fontsize=10.3)
arrow(95.5, 91.5)
diamond(85.5, "Commande lisible\n& complète ?")
arrow(80, 76.5)
box(72, "2.  Croisement avec le master data (IA)\nn° client « Clé 1 »  +  confirmation / correction des SKU\nvia le catalogue du client",
    BLUE_F, BLUE_E, fontsize=10.3, h=8.2)
arrow(67.8, 64.5)
diamond(58.5, "Client trouvé &\nproduits au\ncatalogue ?")
arrow(52.8, 49.5)
box(45, "3.  Commande OK → le PDF est renommé « Client - JJ-MM-AAAA »\net déplacé dans « Commandes-Done » ; la ligne est ajoutée au lot",
    BLUE_F, BLUE_E, fontsize=10.3)
arrow(41.5, 38.5)
box(37, "4.  Génération de l'Excel CCI consolidé dans « Uppload-CCI »\n(1 ligne / commande — SKU douteux et Clé 1 vide surlignés en JAUNE)",
    BLUE_F, BLUE_E, h=8.2, fontsize=10.3)

# --- Branche A-revoir (rejet) : boîte latérale partagée -------------------
ax.add_patch(FancyBboxPatch((72, 55), 25, 20,
             boxstyle="round,pad=0.2,rounding_size=1.2", linewidth=1.8,
             edgecolor=ORANGE_E, facecolor=ORANGE_F, zorder=3))
ax.text(84.5, 72.5, "Dossier « A-revoir »  (revue humaine)", ha="center",
        va="center", fontsize=9.6, weight="bold", color=ORANGE_E)
ax.text(84.5, 63.5,
        "Document illisible / incomplet,\nclient introuvable, ou produit\nhors catalogue.\n\n"
        "→ PDF renommé + déplacé\n→ Excel « rapport d'erreurs »\n   (fichier · date · observation)",
        ha="center", va="center", fontsize=8.6, color="#7a3b10")
# flèches "Non" des deux décisions vers la boîte A-revoir
elbow(60, 85.5, 72, 70, color=ORANGE_E)
ax.text(64.5, 89, "Non", fontsize=9, color=ORANGE_E, weight="bold")
elbow(60, 58.5, 72, 60, color=ORANGE_E)
ax.text(64.5, 55.5, "Non", fontsize=9, color=ORANGE_E, weight="bold")
# libellés "Oui"
ax.text(46.6, 78, "Oui", fontsize=9, color=GREEN_E, weight="bold")
ax.text(46.6, 51, "Oui", fontsize=9, color=GREEN_E, weight="bold")

# ===== ③ VÉRIFICATION & SAISIE ===========================================
arrow(32.9, 30, x=CX)
box(26, "5.  Le gestionnaire vérifie TOUT l'Excel — toutes les lignes,\npas seulement les cellules jaunes",
    ORANGE_F, ORANGE_E, bold=True)
arrow(22.5, 19.5)
box(16.5, "6.  Reprise manuelle des commandes du dossier « A-revoir »\n7.  Saisie / import de l'Excel dans ProConcept → création des CCI (modifications possibles)",
    ORANGE_F, ORANGE_E, h=8.4)
# lien A-revoir -> reprise humaine
elbow(84.5, 55, 68.5, 17.5, color=ORANGE_E)
arrow(12.3, 9.5)
box(6, "CCI créées dans ProConcept", GREEN_F, GREEN_E, bold=True, style="stadium", w=40)

# ===== Bandeau bas (amont / parallèle) ===================================
ax.add_patch(FancyBboxPatch((6, 0.2), 88, 3.4,
             boxstyle="round,pad=0.2,rounding_size=0.8", linewidth=1.6,
             edgecolor=TRB_BLUE, facecolor="#F2F6FB", linestyle=(0,(5,3)), zorder=3))
ax.text(50, 1.9,
        "EN AMONT — le master data (clients « Clé 1 » + catalogues) est rafraîchi périodiquement depuis l'historique des ventes : "
        "plus il est à jour, plus l'outil résout de clients et de SKU automatiquement.",
        ha="center", va="center", fontsize=9.2, color=TRB_BLUE)

plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
import os as _os
out = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "flowchart_cci.png")
fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=0.15, facecolor="white")
print("OK:", out)

# Sources des documents TRB (Outil CCI)

Scripts qui génèrent le flowchart et les deux documents Word décrivant **notre** outil
CCI (à ne pas confondre avec les documents `*_v3.docx` de l'agent Copilot / Cowork,
qui décrivent l'autre démarche).

## Fichiers produits (dans le dossier parent)

- `Cahier_des_charges_Outil_CCI_v1.docx`
- `Guide_utilisateur_Outil_CCI_v1.docx`
- `flowchart_cci.png` — le schéma « Cycle de vie d'une commande » (bleu = automatique,
  orange = humain, vert = début/fin, jaune = décision), intégré dans les deux documents.

## Régénérer

Dépendances : `python-docx`, `matplotlib` (`pip install python-docx matplotlib`).

```bash
cd _sources
python3 flowchart.py     # (re)génère flowchart_cci.png
python3 gen_cahier.py    # (re)génère le cahier des charges
python3 gen_guide.py     # (re)génère le guide utilisateur
```

- `docgen_common.py` — helpers de style Word partagés (couleurs TRB, tables, encadrés).
- `flowchart.py` — le schéma (matplotlib). Modifier les libellés/étapes ici.
- `gen_cahier.py` / `gen_guide.py` — le contenu des deux documents.

> Pour exporter en PDF : ouvrir le `.docx` dans Word puis « Enregistrer sous → PDF ».

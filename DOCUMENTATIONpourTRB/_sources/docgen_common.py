# -*- coding: utf-8 -*-
"""Helpers partagés pour générer les deux documents Word TRB (style collègue)."""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TRB_BLUE = RGBColor(0x15, 0x57, 0x8F)
TRB_BLUE_HEX = "15578F"
DARK = RGBColor(0x20, 0x20, 0x20)
GREY = RGBColor(0x59, 0x59, 0x59)
GREEN = RGBColor(0x54, 0x82, 0x35)
ORANGE = RGBColor(0xC5, 0x5A, 0x11)
HEAD_FILL = "15578F"
ALT_FILL = "EAF1FB"
CALLOUT_FILL = "FCE4D6"    # orange clair (garde-fous / important)
CALLOUT_EDGE = "C55A11"
INFO_FILL = "E2EFD9"       # vert clair


def new_doc():
    doc = Document()
    n = doc.styles["Normal"]
    n.font.name = "Calibri"
    n.font.size = Pt(10.5)
    n.paragraph_format.space_after = Pt(5)
    for lvl, size in ((1, 15), (2, 12.5)):
        st = doc.styles[f"Heading {lvl}"]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.color.rgb = TRB_BLUE
        st.font.bold = True
    # marges un peu resserrées
    for s in doc.sections:
        s.left_margin = Inches(0.9)
        s.right_margin = Inches(0.9)
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
    return doc


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def cell_text(cell, text, *, bold=False, white=False, color=None, size=None,
              align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    if align:
        p.alignment = align
    parts = text.split("\n")
    for i, seg in enumerate(parts):
        if i:
            p = cell.add_paragraph()
        run = p.add_run(seg)
        run.bold = bold
        if white:
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        elif color is not None:
            run.font.color.rgb = color
        if size:
            run.font.size = Pt(size)


def para(doc, text="", *, bold=False, italic=False, color=None, size=None,
         align=None, space_after=5, space_before=0, runs=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    if align:
        p.alignment = align
    if runs:
        for t, b in runs:
            r = p.add_run(t)
            r.bold = b
    elif text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        if color is not None:
            r.font.color.rgb = color
        if size:
            r.font.size = Pt(size)
    return p


def bullet(doc, runs, *, style="List Bullet"):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(2)
    if isinstance(runs, str):
        runs = [(runs, False)]
    for t, b in runs:
        p.add_run(t).bold = b
    return p


def req(doc, code, title, body):
    """Ligne d'exigence : « EF-1  Titre — corps »."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"{code}  ")
    r.bold = True
    r.font.color.rgb = TRB_BLUE
    r2 = p.add_run(f"{title} — ")
    r2.bold = True
    p.add_run(body)
    return p


def callout(doc, text, *, fill=CALLOUT_FILL, edge=CALLOUT_EDGE, label=None):
    """Encadré une-cellule (bandeau important), comme les tableaux 1x1 de la collègue."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.rows[0].cells[0]
    shade(cell, fill)
    _set_borders(t, edge)
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    if label:
        rr = p.add_run(label + "  ")
        rr.bold = True
        rr.font.color.rgb = RGBColor(int(edge[0:2],16), int(edge[2:4],16), int(edge[4:6],16))
    p.add_run(text)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def _set_borders(table, hex_color="BFBFBF"):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "6")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), hex_color)
        borders.append(e)
    tblPr.append(borders)


def table(doc, headers, rows, *, widths=None, zebra=True, header_fill=HEAD_FILL):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_borders(t)
    for i, h in enumerate(headers):
        cell_text(t.rows[0].cells[i], h, bold=True, white=True)
        shade(t.rows[0].cells[i], header_fill)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cell_text(cells[i], str(val))
            if zebra and ri % 2 == 1:
                shade(cells[i], ALT_FILL)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def kv_block(doc, rows, *, label_w=1.7, val_w=4.8):
    """Table clé/valeur sans en-tête ni bordures visibles (bloc d'infos de titre)."""
    t = doc.add_table(rows=len(rows), cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(rows):
        c0, c1 = t.rows[i].cells
        cell_text(c0, k, bold=True, color=TRB_BLUE, size=10)
        cell_text(c1, v, size=10)
        c0.width = Inches(label_w)
        c1.width = Inches(val_w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def title_block(doc, lines):
    """lines = liste de (texte, {size, color, bold, italic, space_after})."""
    for text, opt in lines:
        para(doc, text, bold=opt.get("bold", False), italic=opt.get("italic", False),
             color=opt.get("color"), size=opt.get("size"),
             align=WD_ALIGN_PARAGRAPH.CENTER,
             space_after=opt.get("space_after", 4),
             space_before=opt.get("space_before", 0))


def figure(doc, img_path, caption, *, width_in=6.5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.add_run().add_picture(img_path, width=Inches(width_in))
    cap = para(doc, caption, italic=True, color=GREY, size=9.5,
               align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    return cap


def sommaire(doc, entries):
    para(doc, "Cliquez sur un titre pour accéder au chapitre correspondant.",
         italic=True, color=GREY, size=9.5, space_after=6)
    for text, sub in entries:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.left_indent = Inches(0.25 if sub else 0)
        r = p.add_run(text)
        r.bold = not sub
        if not sub:
            r.font.color.rgb = TRB_BLUE
        else:
            r.font.color.rgb = GREY
            r.font.size = Pt(10)

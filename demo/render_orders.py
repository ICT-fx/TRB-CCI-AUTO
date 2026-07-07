#!/usr/bin/env python3
"""Rend les 25 commandes truquées en PDF depuis demo/faked_orders.json.

Chaque commande est composée en HTML selon son `skin` (famille de mise en page
reprenant la structure d'un original), puis imprimée en PDF via **Chrome headless**.

Usage :
    python3 demo/render_orders.py                 # rend tout dans demo/commandes_fake/
    python3 demo/render_orders.py Austria PL      # rend seulement ces `out`

Prérequis : Google Chrome (macOS par défaut). Surcharge possible via $CHROME.
"""
import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "commandes_fake")
HTML_DIR = os.path.join(OUT_DIR, "_html")

CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def e(s):
    return html.escape(str(s if s is not None else ""))


def money(v):
    return f"{v:,.2f}"


def addr_html(block, bold_name=True):
    name = f'<div class="name">{e(block["name"])}</div>' if bold_name else e(block["name"]) + "<br>"
    lines = "<br>".join(e(x) for x in block.get("lines", []))
    return f'{name}<div class="addr">{lines}</div>'


def contact_html(block):
    bits = []
    if block.get("contact"):
        bits.append(f'Contact : {e(block["contact"])}')
    if block.get("tel"):
        bits.append(f'Tel. : {e(block["tel"])}')
    return '<div class="contact">' + "<br>".join(bits) + "</div>" if bits else ""


def lines_total(o):
    return sum(ln["qty"] * ln["unit_price"] for ln in o["lines"])


# --------------------------------------------------------------------------- #
#  SKINS — chaque fonction renvoie le HTML interne d'une page                  #
# --------------------------------------------------------------------------- #

def skin_sap(o):
    cur = e(o["currency"])
    rows = ""
    for i, ln in enumerate(o["lines"], 1):
        rows += (
            f'<tr><td class="c">{i}</td><td class="c">{e(ln["sku"])}</td>'
            f'<td>{e(ln["designation"])}</td><td class="c">{e(o["requested_delivery_date"])}</td>'
            f'<td class="r">{ln["qty"]}</td><td class="c">BOX</td>'
            f'<td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="r">{money(ln["qty"]*ln["unit_price"])}</td></tr>'
        )
    meta = [
        ("PO No.", o["partner_reference"]), ("PO Date", o["order_date"]),
        ("Currency", cur), ("Delivery Date", o["requested_delivery_date"]),
    ]
    meta_html = "".join(f'<div><span>{e(k)}</span>: {e(v)}</div>' for k, v in meta)
    return f"""
    <div class="sap-head">
      <div class="letter">{addr_html(o["sender"])}</div>
      <div class="potitle">PURCHASE ORDER</div>
    </div>
    <div class="sap-meta">
      <div class="mbox"><div class="lbl">Invoice To</div>{addr_html(o["recipient"])}</div>
      <div class="mbox kv">{meta_html}</div>
    </div>
    <table class="grid">
      <thead><tr><th>No</th><th>Material<br>Code</th><th>Description</th>
        <th>Arrival<br>Date</th><th>Quantity</th><th>UoM</th>
        <th>Unit<br>Price</th><th>Amount</th></tr></thead>
      <tbody>{rows}
        <tr class="tot"><td colspan="7" class="r">Total {cur}</td>
          <td class="r">{money(lines_total(o))}</td></tr>
      </tbody>
    </table>
    <div class="notes"><b>Notes:</b> {e(o["notes"])}</div>
    """


def skin_trb_orderform(o):
    cur = e(o["currency"])
    rows = ""
    for ln in o["lines"]:
        rows += (
            f'<tr><td>{e(ln["designation"])}</td><td class="c">{e(ln["sku"])}</td>'
            f'<td class="c">{ln["qty"]}</td><td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="c">{cur}</td></tr>'
        )
    # complète le tableau avec des lignes vides (comme les formulaires originaux)
    for _ in range(max(0, 6 - len(o["lines"]))):
        rows += '<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td></tr>'
    return f"""
    <div class="of-title">O R D E R &nbsp; F O R M</div>
    <div class="of-redbox">
      <b>To be addressed to {e(o["recipient"]["name"])}</b><br>
      {"<br>".join(e(x) for x in o["recipient"]["lines"])}
    </div>
    <div class="of-row2">
      <div class="of-cell"><div class="lbl">Order date / Date commande</div>
        <div class="box ctr"><b>{e(o["order_date"])}</b></div></div>
      <div class="of-cell"><div class="lbl">Order No. / Commande No.</div>
        <div class="box ctr"><b>{e(o["partner_reference"])}</b></div></div>
    </div>
    <div class="of-row2">
      <div class="of-cell"><div class="lbl">Client</div>
        <div class="box">{addr_html(o["sender"])}{contact_html(o["sender"])}</div></div>
      <div class="of-cell"><div class="lbl">Delivery address / Adresse de livraison</div>
        <div class="box">{addr_html(o["sender"], bold_name=False)}</div></div>
    </div>
    <div class="of-row2">
      <div class="of-cell"><div class="lbl">Invoicing address / Adresse facturation</div>
        <div class="box">{addr_html(o["sender"], bold_name=False)}</div></div>
      <div class="of-cell"><div class="lbl">Delivery date / Délai de livraison désiré</div>
        <div class="box ctr"><b>{e(o["requested_delivery_date"])}</b></div></div>
    </div>
    <table class="grid of-tbl">
      <thead><tr><th>Item – Product / Article – Produit</th><th>Ref.</th>
        <th>Quantity / Quantité</th><th>Unit Price / Prix unitaire</th>
        <th>Currency / Monnaie</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="lbl" style="margin-top:8px">Remarks / Remarques</div>
    <div class="box remarks">{e(o["notes"])}</div>
    <div class="sign">Signature: ____________________</div>
    """


def skin_invoice(o):
    cur = e(o["currency"])
    es = o["lang"] == "es"
    title = "ORDEN DE COMPRA" if es else "PURCHASE ORDER"
    rows = ""
    for ln in o["lines"]:
        rows += (
            f'<tr><td class="c">{e(ln["sku"])}</td><td>{e(ln["designation"])}</td>'
            f'<td class="c">{ln["qty"]}</td><td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="r">{money(ln["qty"]*ln["unit_price"])}</td></tr>'
        )
    lbls = (("Código", "Descripción", "Cant", "Precio", "Total") if es
            else ("Code", "Description", "Qty", "Unit Price", "Total"))
    prov = "Proveedor" if es else "Supplier"
    return f"""
    <div class="inv-head">
      <div>{addr_html(o["sender"])}<div class="addr">{e(o["sender"].get("tel",""))}</div></div>
      <div class="inv-title">{title}</div>
    </div>
    <div class="inv-meta">
      <div>{'Fecha' if es else 'Date'}: <b>{e(o["order_date"])}</b> &nbsp;|&nbsp;
           N°: <b>{e(o["partner_reference"])}</b> &nbsp;|&nbsp;
           {'Moneda' if es else 'Currency'}: <b>{cur}</b> &nbsp;|&nbsp;
           {'Entrega' if es else 'Delivery date'}: <b>{e(o["requested_delivery_date"])}</b></div>
      <div class="prov"><span class="lbl">{prov}:</span> {addr_html(o["recipient"], bold_name=False)}</div>
    </div>
    <table class="grid">
      <thead><tr><th>{lbls[0]}</th><th>{lbls[1]}</th><th>{lbls[2]}</th>
        <th>{lbls[3]}</th><th>{lbls[4]}</th></tr></thead>
      <tbody>{rows}
        <tr class="tot"><td colspan="4" class="r">{'TOTAL' } {cur}</td>
          <td class="r">{money(lines_total(o))}</td></tr>
      </tbody>
    </table>
    <div class="notes">{e(o["notes"])}</div>
    <div class="inv-foot">{e(o["sender"]["name"])} — {" · ".join(e(x) for x in o["sender"]["lines"])}</div>
    """


def skin_grid(o):
    cur = e(o["currency"])
    rows = ""
    for ln in o["lines"]:
        rows += (
            f'<tr><td class="c">{e(ln["sku"])}</td><td>{e(ln["designation"])}</td>'
            f'<td class="r">{ln["qty"]}</td><td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="r">{money(ln["qty"]*ln["unit_price"])}</td></tr>'
        )
    return f"""
    <div class="potitle grid-title">PURCHASE ORDER</div>
    <div class="grid-two">
      <div class="gbox"><div class="ghdr">VENDOR / SHIP TO</div>{addr_html(o["recipient"])}</div>
      <div class="gbox"><div class="ghdr">BILL TO</div>{addr_html(o["sender"])}
        {contact_html(o["sender"])}</div>
    </div>
    <div class="grid-meta">
      <div><span>DATE</span>{e(o["order_date"])}</div>
      <div><span>P.O. #</span>{e(o["partner_reference"])}</div>
      <div><span>SHIP VIA</span>AIR</div>
      <div><span>CURRENCY</span>{cur}</div>
      <div><span>DELIVERY</span>{e(o["requested_delivery_date"])}</div>
    </div>
    <table class="grid">
      <thead><tr><th>Item #</th><th>Description</th><th>QTY</th>
        <th>Unit Price</th><th>Total</th></tr></thead>
      <tbody>{rows}
        <tr class="tot"><td colspan="4" class="r">TOTAL {cur}</td>
          <td class="r">{money(lines_total(o))}</td></tr>
      </tbody>
    </table>
    <div class="notes"><b>Terms & Conditions:</b> {e(o["notes"])}</div>
    """


def skin_letter(o):
    cur = e(o["currency"])
    rows = ""
    for i, ln in enumerate(o["lines"], 1):
        rows += (
            f'<tr><td class="c">{i}</td><td class="c">{e(ln["sku"])}</td>'
            f'<td>{e(ln["designation"])}</td><td class="r">{ln["qty"]}</td>'
            f'<td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="r">{money(ln["qty"]*ln["unit_price"])}</td></tr>'
        )
    s = o["sender"]
    kv = [("Origin", s["name"]), ("Shipment", o["requested_delivery_date"]),
          ("Payment", "T/T"), ("Packing", "Export Standard Packing"),
          ("Destination", s["lines"][-1] if s["lines"] else ""),
          ("Remarks", o["notes"])]
    kv_html = "".join(f'<div><span>{e(k)}</span>: {e(v)}</div>' for k, v in kv)
    return f"""
    <div class="lt-name">{e(s["name"])}</div>
    <div class="lt-addr">{" &nbsp; ".join(e(x) for x in s["lines"])}<br>TEL.: {e(s["tel"])}</div>
    <div class="lt-row">
      <div>To.<br>{addr_html(o["recipient"], bold_name=False)}</div>
      <div class="r">DATE : {e(o["order_date"])}<br>Ref No. {e(o["partner_reference"])}</div>
    </div>
    <div class="lt-title">◆ PURCHASE ORDER SHEET ◆</div>
    <p class="lt-p">Gentlemen,<br>We have the pleasure to place an order for the
      undermentioned goods on the terms and conditions set forth hereunder.</p>
    <div class="lt-kv">{kv_html}</div>
    <table class="grid" style="margin-top:14px">
      <thead><tr><th>Item No.</th><th>Ref.</th><th>Description</th>
        <th>Quantity</th><th>Unit Price</th><th>Amount</th></tr></thead>
      <tbody>{rows}
        <tr class="tot"><td colspan="5" class="r">TOTAL {cur}</td>
          <td class="r">{money(lines_total(o))}</td></tr>
      </tbody>
    </table>
    <div class="lt-sign">Yours faithfully,<br><br>{e(s.get("contact",""))}<br>{e(s["name"])}</div>
    """


def skin_trb_po(o):
    cur = e(o["currency"])
    rows = ""
    for ln in o["lines"]:
        rows += (
            f'<tr><td>{e(ln["designation"])}</td><td class="c">{e(ln["sku"])}</td>'
            f'<td class="c">{ln["qty"]}</td><td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="c">{cur}</td></tr>'
        )
    return f"""
    <div class="trbpo-top">
      <div class="trb-logo">TRB<span>Chemedica</span></div>
      <div class="potitle">PURCHASE ORDER</div>
    </div>
    <div class="of-row2">
      <div class="of-cell"><div class="lbl">Order date</div>
        <div class="box"><b>Date : {e(o["order_date"])}</b></div></div>
      <div class="of-cell"><div class="lbl">Order No.</div>
        <div class="box"><b>PO/N° {e(o["partner_reference"])}</b></div></div>
    </div>
    <div class="of-row2">
      <div class="of-cell"><div class="lbl">Client</div>
        <div class="box">{addr_html(o["sender"])}{contact_html(o["sender"])}</div></div>
      <div class="of-cell"><div class="lbl">Delivery address</div>
        <div class="box">{addr_html(o["recipient"], bold_name=False)}</div></div>
    </div>
    <div class="of-row2">
      <div class="of-cell"><div class="lbl">Means of transport</div>
        <div class="box"><b>By : Airfreight</b></div></div>
      <div class="of-cell"><div class="lbl">Delivery date</div>
        <div class="box"><b>Shipped date : {e(o["requested_delivery_date"])}</b></div></div>
    </div>
    <table class="grid of-tbl">
      <thead><tr><th>Item – Product</th><th>Ref.</th><th>Quantity</th>
        <th>Unit Price</th><th>Currency</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="lbl" style="margin-top:8px">Remark</div>
    <div class="box remarks">{e(o["notes"])}</div>
    <div class="sign">For and on behalf of {e(o["sender"]["name"])}<br><br>____________________</div>
    """


def skin_modern(o):
    cur = e(o["currency"])
    rows = ""
    for i, ln in enumerate(o["lines"], 1):
        rows += (
            f'<tr><td class="c">{i}</td><td class="c">{e(ln["sku"])}</td>'
            f'<td>{e(ln["designation"])}</td><td class="r">{ln["qty"]}</td>'
            f'<td class="c">BOX</td><td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="r">{money(ln["qty"]*ln["unit_price"])}</td></tr>'
        )
    return f"""
    <div class="mod-head">
      <div class="trb-logo">TRB<span>Chemedica</span></div>
      <div class="mod-sender">{addr_html(o["sender"])}
        <div class="addr">Tel: {e(o["sender"].get("tel",""))}</div></div>
    </div>
    <div class="mod-meta">
      <div><b>Purchase Order:</b> {e(o["partner_reference"])}<br>
           <b>Date:</b> {e(o["order_date"])}<br>
           <b>Delivery Date:</b> {e(o["requested_delivery_date"])}</div>
      <div class="r"><b>Currency:</b> {cur}<br><b>Payment Terms:</b> 90 days</div>
    </div>
    <div class="grid-two">
      <div class="gbox"><div class="ghdr">Billing Address</div>{addr_html(o["recipient"])}</div>
      <div class="gbox"><div class="ghdr">Delivery Address</div>{addr_html(o["sender"], bold_name=False)}</div>
    </div>
    <table class="grid" style="margin-top:10px">
      <thead><tr><th>No</th><th>Item Code</th><th>Description</th><th>Qty</th>
        <th>UoM</th><th>Price/Unit</th><th>Total Price</th></tr></thead>
      <tbody>{rows}
        <tr class="tot"><td colspan="6" class="r">Total Payable {cur}</td>
          <td class="r">{money(lines_total(o))}</td></tr>
      </tbody>
    </table>
    <div class="notes">{e(o["notes"])}</div>
    <div class="sign r">Authorised Signature ____________________</div>
    """


def skin_dotmatrix(o):
    cur = e(o["currency"])
    rows = ""
    for i, ln in enumerate(o["lines"], 1):
        rows += (
            f'<tr><td class="c">{i}</td><td class="c">{e(ln["sku"])}</td>'
            f'<td>{e(ln["designation"])}</td><td class="r">{ln["qty"]}</td>'
            f'<td class="c">U</td><td class="c">{e(o["requested_delivery_date"])}</td>'
            f'<td class="r">{money(ln["unit_price"])}</td>'
            f'<td class="r">{money(ln["qty"]*ln["unit_price"])}</td></tr>'
        )
    return f"""
    <div class="dm-head">
      <div>{addr_html(o["sender"])}</div>
      <div class="dm-title">{e(o["sender"]["name"])}</div>
    </div>
    <div class="dm-to">
      {addr_html(o["recipient"], bold_name=False)}
    </div>
    <div class="dm-cmd">Commande N° {e(o["partner_reference"])}
      &nbsp;&nbsp; Casablanca le, {e(o["order_date"])}</div>
    <div class="dm-modes">
      Mode de livraison : CIF &nbsp; | &nbsp; Devise : {cur} &nbsp; | &nbsp;
      Règlement : 90 jours net<br>
      <b>Date de livraison souhaitée : {e(o["requested_delivery_date"])}</b>
    </div>
    <table class="grid dm-tbl">
      <thead><tr><th>POS</th><th>Code</th><th>Désignation</th><th>Quantité</th>
        <th>Unité</th><th>Livraison</th><th>Prix Unitaire</th><th>Montant</th></tr></thead>
      <tbody>{rows}
        <tr class="tot"><td colspan="7" class="r">MONTANT NET COMMANDE ({cur})</td>
          <td class="r">{money(lines_total(o))}</td></tr>
      </tbody>
    </table>
    <div class="notes">{e(o["notes"])}</div>
    """


SKINS = {
    "sap": skin_sap, "trb_orderform": skin_trb_orderform, "invoice": skin_invoice,
    "grid": skin_grid, "letter": skin_letter, "trb_po": skin_trb_po,
    "modern": skin_modern, "dotmatrix": skin_dotmatrix,
}

CSS = """
@page { size: A4; margin: 14mm; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 10.5px; color: #111;
       line-height: 1.35; --accent: #1f6fb2; --accent-soft: #eef2f6; }
.name { font-weight: 700; } .addr { color: #222; }
.lbl { font-size: 9.5px; color: #333; margin-bottom: 2px; }
.c { text-align: center; } .r { text-align: right; }
table.grid { width: 100%; border-collapse: collapse; margin-top: 10px; }
table.grid th { background: var(--accent-soft); border: 1px solid #9aa7b4;
                border-bottom: 2px solid var(--accent); padding: 4px 6px;
                font-size: 9.5px; text-align: center; }
table.grid td { border: 1px solid #9aa7b4; padding: 4px 6px; vertical-align: top; }
table.grid tr.tot td { font-weight: 700; background: var(--accent-soft); }
.notes { margin-top: 10px; font-size: 9.5px; color: #333; }
.box { border: 1px solid #333; padding: 6px 8px; min-height: 20px; }
.box.ctr { text-align: center; }
.sign { margin-top: 22px; font-size: 10px; }
.trb-logo { font-weight: 800; font-size: 26px; color: var(--accent); letter-spacing: 1px; }
.trb-logo span { display:block; font-size: 9px; font-weight: 600; color:var(--accent); letter-spacing:0; }
.potitle { font-size: 18px; font-weight: 800; letter-spacing: 2px; text-align: right; color: var(--accent); }
/* sap */
.sap-head { display:flex; justify-content: space-between; align-items: flex-start;
            border-bottom: 2px solid var(--accent); padding-bottom: 8px; }
.sap-meta { display:flex; gap: 10px; margin-top: 10px; }
.sap-meta .mbox { flex:1; border:1px solid #333; padding:6px 8px; }
.sap-meta .lbl { font-weight:700; }
.kv div { font-size: 10px; } .kv span { display:inline-block; width: 90px; color:#333; }
/* order form */
.of-title { text-align:center; font-size: 22px; font-weight: 800; letter-spacing: 4px;
            margin: 4px 0 10px; color: var(--accent); }
.of-redbox { border:1px solid #c33; color:#c00; text-align:center; padding:6px;
             font-size: 10px; margin-bottom: 10px; }
.of-row2 { display:flex; gap: 10px; margin-bottom: 8px; }
.of-cell { flex:1; } .of-cell .box { min-height: 54px; }
.contact { margin-top: 6px; font-size: 9.5px; color:#333; }
table.of-tbl th:first-child { text-align:left; }
.remarks { min-height: 40px; }
/* invoice */
.inv-head { display:flex; justify-content: space-between; align-items:flex-start;
            border-bottom: 2px solid var(--accent); padding-bottom: 6px; }
.inv-title { font-size: 17px; font-weight: 800; letter-spacing: 1px; color: var(--accent); }
.inv-meta { margin-top: 8px; } .inv-meta .prov { margin-top: 6px; }
.inv-foot { margin-top: 16px; border-top: 1px solid #999; padding-top: 4px;
            font-size: 8.5px; color:#666; text-align:center; }
/* grid */
.grid-title { text-align:center; margin: 2px 0 10px; color: var(--accent); }
.grid-two { display:flex; gap: 10px; }
.gbox { flex:1; border:1px solid #333; padding:0; }
.ghdr { background:var(--accent-soft); border-bottom:2px solid var(--accent); padding:3px 6px;
        font-weight:700; font-size: 9.5px; text-align:center; }
.gbox .name, .gbox .addr, .gbox .contact { padding: 0 6px; } .gbox .name { padding-top:4px; }
.gbox .contact { padding-bottom: 4px; }
.grid-meta { display:flex; gap: 0; margin-top: 10px; border:1px solid #333; }
.grid-meta div { flex:1; border-right:1px solid #333; padding:4px 6px; font-size:9.5px; }
.grid-meta div:last-child { border-right: none; }
.grid-meta span { display:block; font-weight:700; font-size:8.5px; color:#333; }
/* letter */
.lt-name { text-align:center; font-size: 24px; font-weight: 800; font-family: 'Times New Roman', serif; }
.lt-addr { text-align:center; font-size: 10px; margin-bottom: 12px; font-family:'Times New Roman',serif; }
.lt-row { display:flex; justify-content: space-between; font-family:'Times New Roman',serif; }
.lt-title { text-align:center; font-weight:800; font-size: 15px; margin: 12px 0;
            font-family:'Times New Roman',serif; color: var(--accent); }
.lt-p { font-family:'Times New Roman',serif; }
.lt-kv div { font-family:'Times New Roman',serif; } .lt-kv span { display:inline-block; width: 90px; }
.lt-sign { margin-top: 20px; text-align:right; font-family:'Times New Roman',serif; }
table.grid.lt td, .lt table.grid td { font-family:'Times New Roman',serif; }
/* trb po */
.trbpo-top { display:flex; justify-content: space-between; align-items:center;
             border-bottom: 2px solid var(--accent); padding-bottom: 6px; margin-bottom: 10px; }
/* modern */
.mod-head { display:flex; justify-content: space-between; align-items:flex-start; }
.mod-sender { text-align:right; font-size: 9.5px; }
.mod-meta { display:flex; justify-content: space-between; margin: 12px 0;
            border-top:2px solid var(--accent); border-bottom:2px solid var(--accent); padding: 6px 0; }
/* dot matrix */
.dm-head, .dm-to, .dm-cmd, .dm-modes, .dm-tbl td, .dm-tbl th {
   font-family: 'Courier New', monospace; }
.dm-head { display:flex; justify-content: space-between; align-items:flex-start;
           border-left: 6px dotted #999; border-right: 6px dotted #999; padding: 6px 10px; }
.dm-title { font-weight: 800; font-size: 18px; letter-spacing: 2px; color: var(--accent); }
.dm-to { margin: 10px; } .dm-cmd { font-weight:700; margin: 8px 10px; }
.dm-modes { margin: 0 10px 8px; font-size: 9.5px; }
"""


# Diversité visuelle : chaque commande reçoit une couleur d'accent + une police,
# pour que deux commandes de même « skin » ne se ressemblent pas.
_ACCENTS = [
    ("#1f6fb2", "#e7f0f8"), ("#2e7d32", "#e8f3e9"), ("#8e24aa", "#f3e8f6"),
    ("#c62828", "#fbe9e9"), ("#00838f", "#e0f0f1"), ("#ef6c00", "#fbeddd"),
    ("#37474f", "#eceff1"), ("#5d4037", "#efe8e6"), ("#283593", "#e8eaf6"),
    ("#ad1457", "#fbe6ee"), ("#455a64", "#eceff1"), ("#6a1b9a", "#f2e7f7"),
    ("#00695c", "#e0efec"), ("#bf360c", "#fbe7df"),
]
_FONTS = [
    "Arial, Helvetica, sans-serif",
    "'Trebuchet MS', Verdana, sans-serif",
    "'Georgia', 'Times New Roman', serif",
    "'Tahoma', Geneva, sans-serif",
    "'Palatino Linotype', 'Book Antiqua', serif",
    "Calibri, 'Segoe UI', sans-serif",
]


def render_one(o, idx=0):
    accent, soft = _ACCENTS[idx % len(_ACCENTS)]
    # police par commande (les skins letter/dotmatrix gardent la leur via leur CSS)
    font = _FONTS[(idx * 3 + 1) % len(_FONTS)]
    style = f"--accent:{accent}; --accent-soft:{soft}; font-family:{font};"
    body = SKINS[o["skin"]](o)
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{e(o['out'])}</title><style>{CSS}</style></head>
<body class="{e(o['skin'])}" style="{style}">{body}</body></html>"""
    os.makedirs(HTML_DIR, exist_ok=True)
    html_path = os.path.join(HTML_DIR, o["out"] + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    pdf_path = os.path.join(OUT_DIR, o["out"] + ".pdf")
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--run-all-compositor-stages-before-draw", "--virtual-time-budget=2000",
         f"--print-to-pdf={pdf_path}", "file://" + html_path],
        check=True, capture_output=True,
    )
    return pdf_path


def main():
    with open(os.path.join(HERE, "faked_orders.json"), encoding="utf-8") as f:
        orders = json.load(f)
    # index stable (position dans la liste complète) -> accent/police déterministes,
    # même quand on ne rend qu'un sous-ensemble.
    indexed = list(enumerate(orders))
    only = set(sys.argv[1:])
    if only:
        indexed = [(i, o) for i, o in indexed if o["out"] in only]
    os.makedirs(OUT_DIR, exist_ok=True)
    for i, o in indexed:
        p = render_one(o, i)
        print(f"✓ {o['skin']:14} {o['outcome']:13} → {os.path.basename(p)}")
    print(f"\n{len(indexed)} PDF dans {OUT_DIR}")


if __name__ == "__main__":
    main()

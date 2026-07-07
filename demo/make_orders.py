#!/usr/bin/env python3
"""Génère demo/faked_orders.json — la SOURCE DE VÉRITÉ des 25 commandes truquées.

Chaque entrée décrit une commande : client fictif, code (7 chiffres), réf. PO,
dates, devise, blocs d'adresse, lignes produit (vraies désignations TRB + vrai SKU
4 chiffres, quantités 1–30, prix délirants), le `skin` (famille de mise en page)
et l'`outcome` attendu de la démo (pass / fail_client / fail_product).

Les couples (sku, designation) sont de VRAIES paires de la master data (backup),
pour rester cohérents et réalistes. Seuls le nom/code client, la réf, les dates,
les quantités et les prix sont fictifs.

Lancer :  python3 demo/make_orders.py   → (ré)écrit demo/faked_orders.json
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Destinataires TRB réels (non secrets — c'est le propriétaire de l'outil)
TRB_INT = {
    "name": "TRB CHEMEDICA INTERNATIONAL S.A.",
    "lines": ["Rue Michel-Servet 12", "1206 Geneva", "Switzerland"],
}
TRB_INT_CAROUGE = {
    "name": "TRB CHEMEDICA INTERNATIONAL S.A.",
    "lines": ["Route des Jeunes 33bis", "1227 Carouge GE", "Switzerland"],
}
TRB_AG = {
    "name": "TRB Chemedica AG",
    "lines": ["Otto-Lilienthal-Ring 26", "85622 Feldkirchen", "Germany"],
}
TRB_ME = {
    "name": "TRB Middle East FZE",
    "lines": ["The Offices 4 – One Central", "Dubai World Trade Center", "United Arab Emirates"],
}

# Prix « délirants » (fictifs, hyper-élevés) — piochés par index de ligne
DELIRIOUS = [88888.00, 125000.00, 74250.00, 199990.00, 42600.00,
             312000.00, 96500.00, 158000.00, 249000.00, 61750.00,
             404040.00, 137900.00, 275500.00, 89990.00, 512000.00]


def L(designation, sku, qty, price_idx):
    return {"designation": designation, "sku": sku, "qty": qty,
            "unit_price": DELIRIOUS[price_idx % len(DELIRIOUS)]}


ORDERS = [
    # 1 — AG : TRB AG achète OSTENIL MINI à un fabricant (DE). PASS
    {
        "source": "AG.pdf", "out": "AG", "skin": "sap", "lang": "de",
        "client_name": "Rheintal Pharmazeutika GmbH",
        "sender": {"name": "Rheintal Pharmazeutika GmbH",
                   "lines": ["Otto-Hahn-Strasse 14", "85622 Feldkirchen", "Germany"],
                   "contact": "Franziska Wulf", "tel": "+49 89 4520 118"},
        "recipient": TRB_AG,
        "partner_reference": "LB-26-0349", "order_date": "25.02.2026",
        "requested_delivery_date": "KW 46/2026", "currency": "EUR",
        "notes": "Payment condition 90 days net. Ex works.",
        "lines": [L("OSTENIL MINI 1 - EU-WEST", "1082", 12, 0)],
        "outcome": "pass",
    },
    # 2 — Austria : Ostenil line-up (AT). PASS
    {
        "source": "Austria.pdf", "out": "Austria", "skin": "trb_orderform", "lang": "en",
        "client_name": "Alpenmed Vertriebs GmbH",
        "sender": {"name": "Alpenmed Vertriebs GmbH",
                   "lines": ["Industriezentrum NÖ Süd, Strasse 7", "A-2355 Wiener Neudorf", "Austria"],
                   "contact": "Florian Palmer-Doerner", "tel": "0043 2236 660600 12"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "AT-26-014", "order_date": "10.06.2026",
        "requested_delivery_date": "June 2027", "currency": "EUR",
        "notes": "Prices according to the 2026 price list. Means of transport: Truck.",
        "lines": [
            L("OSTENIL 1 TY - EU-WEST", "1780", 21, 0),
            L("OSTENIL 100 TY - EU-WEST", "1781", 7, 1),
            L("OSTENIL PLUS 1 - EU-WEST", "1013", 16, 2),
            L("OSTENIL MINI 1 - EU-WEST", "1082", 30, 3),
        ],
        "outcome": "pass",
    },
    # 3 — Brazil (TRB Pharma BR). PASS
    {
        "source": "brazil.pdf", "out": "brazil", "skin": "trb_orderform", "lang": "en",
        "client_name": "Farma Atlântico Indústria Ltda",
        "sender": {"name": "Farma Atlântico Indústria Ltda",
                   "lines": ["Rua das Palmeiras, 149", "São Paulo, SP, Brasil", "CEP: 04334-150"],
                   "contact": "Ricardo Benevides", "tel": "+55 11 5588-2500"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "MINI-010627", "order_date": "01.06.2026",
        "requested_delivery_date": "14.06.2027", "currency": "EUR",
        "notes": "Means of transport: Air freight.",
        "lines": [
            L("OSTENIL MINI 1 - EU-WEST", "1082", 24, 4),
            L("OSTENIL 1 - EU-WEST", "0587", 9, 5),
        ],
        "outcome": "pass",
    },
    # 4 — Brudy Lab (ES) — invoice style. PASS
    {
        "source": "brudylab.pdf", "out": "brudylab", "skin": "invoice", "lang": "en",
        "client_name": "Laboratorios Brisamar S.L.U.",
        "sender": {"name": "Laboratorios Brisamar S.L.U.",
                   "lines": ["Riera de Sant Miquel, 3", "08006 Barcelona", "Spain"],
                   "contact": "Compras", "tel": "+34 93 217 0366"},
        "recipient": TRB_INT,
        "partner_reference": "PO-2026-36", "order_date": "16.06.2026",
        "requested_delivery_date": "October 2026", "currency": "EUR",
        "notes": "Delivery in October '26.",
        "lines": [L("VISMED 20 - N", "0687", 24, 6)],
        "outcome": "pass",
    },
    # 5 — Cigalah (UAE) — heavy grid. PASS
    {
        "source": "cigalah drug store.pdf", "out": "cigalah", "skin": "grid", "lang": "en",
        "client_name": "Emirates Crescent Drug Store L.L.C.",
        "sender": {"name": "Emirates Crescent Drug Store L.L.C.",
                   "lines": ["Nad Al Hamar, 9th Street", "Dubai", "United Arab Emirates"],
                   "contact": "Parin K Rathod", "tel": "+971 50 50 55389"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "POSC-TRB-022026-1", "order_date": "03.04.2026",
        "requested_delivery_date": "May 2026", "currency": "USD",
        "notes": "Please indicate our PO ref in all documents. Incoterm: CIP.",
        "lines": [
            L("VISMED GEL 20 - MENA", "1328", 18, 7),
            L("VISMED 20 - MENA", "1325", 26, 8),
        ],
        "outcome": "pass",
    },
    # 6 — Combiphar (ID) — SAP style. PASS
    {
        "source": "Combiphar.pdf", "out": "Combiphar", "skin": "sap", "lang": "en",
        "client_name": "PT Nusantara Farma Sentosa",
        "sender": {"name": "PT NUSANTARA FARMA SENTOSA",
                   "lines": ["Jl. Jend. Sudirman Kav. 52-53", "Jakarta Selatan 12190", "Indonesia"],
                   "contact": "Procurement", "tel": "(62-21) 293 33031"},
        "recipient": TRB_INT,
        "partner_reference": "4500046167", "order_date": "13.04.2026",
        "requested_delivery_date": "10.02.2027", "currency": "EUR",
        "notes": "Incoterm: CIP Jakarta. Payment: 150 days after AWB date.",
        "lines": [L("ARTRODAR 30 consig. ARG", "1344", 9, 9)],
        "outcome": "pass",
    },
    # 7 — Corporacion AMICELCO (GT) — invoice/orden de compra. PASS
    {
        "source": "Corporacion Am.pdf", "out": "Corporacion_Am", "skin": "invoice", "lang": "es",
        "client_name": "Distribuidora Centroamericana de Farmacia, S.A.",
        "sender": {"name": "Distribuidora Centroamericana de Farmacia, S.A.",
                   "lines": ["5a. Avenida 4-12, Zona 1", "Guatemala, C.A."],
                   "contact": "Compras", "tel": "2238-3581"},
        "recipient": TRB_INT,
        "partner_reference": "260540", "order_date": "07.05.2026",
        "requested_delivery_date": "July 2026", "currency": "USD",
        "notes": "Vía aérea. Términos: 90 días. No enviar mercadería con vencimiento menor a 18 meses.",
        "lines": [L("ARTRODAR 30 consig. ARG", "1344", 22, 10)],
        "outcome": "pass",
    },
    # 8 — Doc G (IT) — FAIL_CLIENT (client absent de la master data)
    {
        "source": "Doc G.pdf", "out": "Doc_G", "skin": "sap", "lang": "it",
        "client_name": "Farmaceutici Aurelia S.r.l.",
        "sender": {"name": "FARMACEUTICI AURELIA S.r.l.",
                   "lines": ["Via Cassia 1201", "00189 Roma", "Italy"],
                   "contact": "Ufficio Acquisti", "tel": "+39 06 3312 8800"},
        "recipient": TRB_INT,
        "partner_reference": "OA-2026-1188", "order_date": "12.05.2026",
        "requested_delivery_date": "September 2026", "currency": "EUR",
        "notes": "Ordine soggetto al Codice Etico e al Modello 231/2001.",
        "lines": [
            L("IDROFLOG 15", "1621", 14, 11),
            L("RELYS Multidose 10 ml (IT)", "1749", 6, 12),
        ],
        "outcome": "fail_client",
    },
    # 9 — Hong Kong (Reig Jofre → Jacobson Medical HK) — order confirmation. PASS
    {
        "source": "Hong kong.pdf", "out": "Hong_kong", "skin": "grid", "lang": "en",
        "client_name": "Jade Harbour Medical (Hong Kong) Ltd.",
        "sender": {"name": "Jade Harbour Medical (Hong Kong) Ltd.",
                   "lines": ["Flat C2, 16/F, Ever Gain Centre", "28 On Muk Street, Shatin", "Hong Kong"],
                   "contact": "Purchasing", "tel": "+852 2601 1234"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "OF-26-0148", "order_date": "29.04.2026",
        "requested_delivery_date": "01.12.2026", "currency": "EUR",
        "notes": "Shipment method: EXW at factory. Payment terms: 60 days.",
        "lines": [L("TENDOACTIVE - HK", "1719", 20, 13)],
        "outcome": "pass",
    },
    # 10 — Kukje (KR) — formal letter. PASS
    {
        "source": "Kukje.pdf", "out": "Kukje", "skin": "letter", "lang": "en",
        "client_name": "Hankuk Medi Pharm Co., Ltd.",
        "sender": {"name": "HANKUK MEDI PHARM CO., LTD.",
                   "lines": ["96-8, Yatab-ro, Bundang-gu", "Seongnam-City, Gyeonggi-do", "Korea"],
                   "contact": "H. J. Lee / General Manager", "tel": "+82 31 781 9081"},
        "recipient": TRB_INT,
        "partner_reference": "KJ261016R-1", "order_date": "26.03.2026",
        "requested_delivery_date": "May 2026", "currency": "EUR",
        "notes": "Destination: Incheon Airport, Korea. Packing: Export Standard Packing.",
        "lines": [L("VISMED MULTI 10 - KOREA", "1313", 28, 14)],
        "outcome": "pass",
    },
    # 11 — Meprofarm (ID) — SAP style. PASS
    {
        "source": "Mephropharm.pdf", "out": "Mephropharm", "skin": "sap", "lang": "en",
        "client_name": "PT Bumi Sehat Farmasi",
        "sender": {"name": "PT BUMI SEHAT FARMASI",
                   "lines": ["Jl. Soekarno Hatta 789", "Bandung 40294", "Indonesia"],
                   "contact": "Purchasing", "tel": "(022) 7805588"},
        "recipient": TRB_INT,
        "partner_reference": "412505560", "order_date": "20.11.2025",
        "requested_delivery_date": "December 2026", "currency": "USD",
        "notes": "Cantumkan No PO pada setiap surat pengantar. Confirm delivery date.",
        "lines": [
            L("OSTENIL 1 TY - EU-WEST", "1780", 19, 0),
            L("OSTENIL PLUS 1 TY - EU-WEST", "1784", 11, 1),
        ],
        "outcome": "pass",
    },
    # 12 — Optimed (SI) — FAIL_PRODUCT (OSTENIL PLUS intrus, hors catalogue Vismed/Visiol)
    {
        "source": "Optimed.pdf", "out": "Optimed", "skin": "trb_orderform", "lang": "en",
        "client_name": "Medikom Adria d.o.o.",
        "sender": {"name": "MEDIKOM ADRIA D.O.O.",
                   "lines": ["Litostrojska cesta 44 c", "1000 Ljubljana", "Slovenia"],
                   "contact": "Naročila", "tel": "+386 1 518 19 77"},
        "recipient": TRB_INT,
        "partner_reference": "PO-2026-09", "order_date": "16.04.2026",
        "requested_delivery_date": "16.09.2026", "currency": "EUR",
        "notes": "EX WORKS. Week no. 38.",
        "lines": [
            L("VISMED GEL 20 - N", "0899", 12, 2),
            L("VISMED LIGHT 15 - N", "0903", 8, 3),
            L("VISMED 20 - N", "0687", 15, 4),
            L("VISMED MULTI 10 - N (INT) std", "1083", 22, 5),
            L("VISIOL 1 - N, ss bkp/can", "1307", 6, 6),
            # ligne INTRUS (hors catalogue de ce client) -> 422 produit hors catalogue
            L("OSTENIL PLUS 1 TY - EU-WEST", "1784", 10, 7),
        ],
        "outcome": "fail_product", "intruder_index": 5,
    },
    # 13 — PL (Poland) — TRB order form. PASS
    {
        "source": "PL.pdf", "out": "PL", "skin": "trb_orderform", "lang": "en",
        "client_name": "Vistula Pharma Sp. z o.o.",
        "sender": {"name": "Vistula Pharma Sp. z o.o.",
                   "lines": ["ul. Belwederska 9A Lok. 5", "00-761 Warszawa", "Poland"],
                   "contact": "Sylwester Szarafin", "tel": "+48 203 83 13"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "02/2026", "order_date": "27.01.2026",
        "requested_delivery_date": "January 2027", "currency": "EUR",
        "notes": "Means of transport: Truck. Split will be done — wholesalers.",
        "lines": [L("OSTENIL MINI 1 - EU-WEST", "1082", 18, 8)],
        "outcome": "pass",
    },
    # 14 — River Pharma (PE) — FAIL_CLIENT
    {
        "source": "river pharma.pdf", "out": "river_pharma", "skin": "invoice", "lang": "es",
        "client_name": "Andes River Pharma S.A.C.",
        "sender": {"name": "ANDES RIVER PHARMA S.A.C.",
                   "lines": ["Av. General Trinidad Morán 1178, Lince", "Lima", "Perú"],
                   "contact": "Compras", "tel": "+51 1 470 0000"},
        "recipient": TRB_INT,
        "partner_reference": "0020-RP-2026", "order_date": "07.05.2026",
        "requested_delivery_date": "July 2026", "currency": "USD",
        "notes": "Moneda: dólares. Condición de pago: contado. Entregar en: Perú.",
        "lines": [L("OSTENIL TENDON 1 - EU-WEST", "1203", 27, 9)],
        "outcome": "fail_client",
    },
    # 15 — Serpin (CY/TR) — FAIL_CLIENT
    {
        "source": "Serpin.pdf", "out": "Serpin", "skin": "trb_orderform", "lang": "en",
        "client_name": "Levant Serapis Dış Ticaret Ltd. Şti.",
        "sender": {"name": "Levant Serapis Dış Ticaret Ltd. Şti.",
                   "lines": ["84 Sht. Mustafa Ruso Caddesi", "K. Kaymakli, Lefkosa", "Mersin-10, Turkey"],
                   "contact": "Naciye Demirciler", "tel": "90 392 227 0253"},
        "recipient": TRB_INT,
        "partner_reference": "NO-2026-2", "order_date": "13.06.2026",
        "requested_delivery_date": "May 2027", "currency": "EUR",
        "notes": "Airport of destination is ERCAN. Means of transport: AIR.",
        "lines": [
            L("VISMED 20 - N", "0687", 25, 10),
            L("VISMED GEL 20 - N", "0899", 12, 11),
            L("VISMED LIGHT 15 - N", "0903", 8, 12),
            L("VISMED MULTI 10 - N (INT) std", "1083", 20, 13),
        ],
        "outcome": "fail_client",
    },
    # 16 — Star International (EG) — Star PO grid. PASS
    {
        "source": "star int.pdf", "out": "star_int", "skin": "grid", "lang": "en",
        "client_name": "Nile Star Medical Co.",
        "sender": {"name": "Nile Star Medical Co.",
                   "lines": ["3A, Maadi Towers, Cornich el Nile", "Maadi, Cairo", "Egypt"],
                   "contact": "Dr. Mamdouh Deif", "tel": "(002) 25247220"},
        "recipient": TRB_INT,
        "partner_reference": "2026/00011", "order_date": "16.02.2026",
        "requested_delivery_date": "December 2026", "currency": "EUR",
        "notes": "Payment: 90 days from invoice. Shipping terms: CIF. Cairo International Airport.",
        "lines": [
            L("OSTENIL 1 - EU-WEST", "0587", 15, 14),
            L("OSTENIL PLUS 1 - EU-WEST", "1013", 23, 0),
            L("OSTENIL MINI 1 - EU-WEST", "1082", 4, 1),
            L("VISCOSEAL 1 SER. - N", "1202", 9, 2),
        ],
        "outcome": "pass",
    },
    # 17 — Synthemedic (MA) — dot-matrix. PASS
    {
        "source": "synthemedic.pdf", "out": "synthemedic", "skin": "dotmatrix", "lang": "fr",
        "client_name": "Atlas Médic S.A.",
        "sender": {"name": "ATLAS MÉDIC S.A.",
                   "lines": ["20-22 Rue Zoubeir Bnou El Aouam", "Roches Noires, 20300 Casablanca", "Maroc"],
                   "contact": "Achats", "tel": "05 22 40 47 90"},
        "recipient": TRB_INT,
        "partner_reference": "20260298", "order_date": "27.10.2025",
        "requested_delivery_date": "01.09.2026", "currency": "EUR",
        "notes": "CIF Coût, Assurance et Fret — Aéroport Mohamed V. 90 jours net.",
        "lines": [L("VISMED MULTI 10 - N (INT) std", "1083", 30, 3)],
        "outcome": "pass",
    },
    # 18 — Thailand — TRB PO. PASS
    {
        "source": "TH.pdf", "out": "TH", "skin": "trb_po", "lang": "en",
        "client_name": "Siam Vision Distribution Ltd.",
        "sender": {"name": "SIAM VISION DISTRIBUTION LTD.",
                   "lines": ["No. 88 The PARQ Building, 9th Floor", "Khlong Toei, Bangkok 10110", "Thailand"],
                   "contact": "Ms. Nipaporn Jitsook", "tel": "66 2 2642010-4"},
        "recipient": TRB_INT,
        "partner_reference": "TRBTH59/2026", "order_date": "27.04.2026",
        "requested_delivery_date": "November 2026", "currency": "EUR",
        "notes": "Incoterm: FCA. Term of payment: 90 days. By Airfreight.",
        "lines": [L("VISLUBE MULTI 10 - THA", "1604", 26, 4)],
        "outcome": "pass",
    },
    # 19 — UK — FAIL_PRODUCT (ARTRODAR intrus, hors catalogue Vismed UK)
    {
        "source": "UK.pdf", "out": "UK", "skin": "grid", "lang": "en",
        "client_name": "Albion Pharma Distribution Ltd",
        "sender": {"name": "Albion Pharma Distribution Ltd",
                   "lines": ["9 Evolution, Lymedale Business Park", "Newcastle-under-Lyme, ST5 9QF", "United Kingdom"],
                   "contact": "Mike Hibbs", "tel": "44 1782 563207"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "PO-4676", "order_date": "11.06.2026",
        "requested_delivery_date": "07.06.2027", "currency": "EUR",
        "notes": "Prices in € Euros. No VAT.",
        "lines": [
            L("VISMED 20 - UK", "1297", 22, 5),
            # ligne INTRUS (hors catalogue de ce client) -> 422 produit hors catalogue
            L("ARTRODAR 30 consig. ARG", "1344", 7, 6),
        ],
        "outcome": "fail_product", "intruder_index": 1,
    },
    # 20 — Vietnam (DKSH) — TRB PO. PASS
    {
        "source": "VT.pdf", "out": "VT", "skin": "trb_po", "lang": "en",
        "client_name": "Mekong Health Distribution Co., Ltd.",
        "sender": {"name": "MEKONG HEALTH DISTRIBUTION CO., LTD.",
                   "lines": ["23 Doc Lap Avenue, VSIP", "Binh Hoa Ward, Ho Chi Minh City", "Vietnam"],
                   "contact": "Ms. Nhi Tran", "tel": "+84 838125737"},
        "recipient": TRB_INT,
        "partner_reference": "TRBVN2026/26", "order_date": "27.05.2026",
        "requested_delivery_date": "February 2027", "currency": "USD",
        "notes": "Under Decree 98, No CE Mark. 80% shelf-life upon arrival. By Airfreight.",
        "lines": [
            L("VISIOL 1 - VN", "1736", 4, 7),
            L("OSTENIL TENDON 1 TY - VN D98", "1874", 10, 8),
            L("OSTENIL PLUS 1 TY - VN D98", "1580", 14, 9),
            L("OSTENIL 1 - VN C30", "1570", 12, 10),
        ],
        "outcome": "pass",
    },
    # 21 — Al Tafaol (QA) — simple forecast table. PASS
    {
        "source": "Al tafaol.pdf", "out": "Al_tafaol", "skin": "modern", "lang": "en",
        "client_name": "Al Wafra Trading Company W.L.L.",
        "sender": {"name": "AL WAFRA TRADING COMPANY W.L.L.",
                   "lines": ["Old Airport St., Bldg No. 10", "Zone No. 45, Doha", "Qatar"],
                   "contact": "Division Manager", "tel": "+974 4465 2773"},
        "recipient": TRB_ME,
        "partner_reference": "FC-Q2-2026", "order_date": "04.11.2025",
        "requested_delivery_date": "Q2-2026", "currency": "USD",
        "notes": "Forecasted order for Q2-2026.",
        "lines": [
            L("OSTENIL PLUS 1 - EU-WEST", "1013", 16, 11),
            L("OSTENIL TENDON 1 - EU-WEST", "1203", 16, 12),
            L("VISMED 20 - MENA", "1325", 29, 13),
            L("VISMED GEL 20 - MENA", "1328", 23, 14),
        ],
        "outcome": "pass",
    },
    # 22 — France (TRB Chemedica SAS Archamps) — TRB order form. PASS
    {
        "source": "france.pdf", "out": "france", "skin": "trb_orderform", "lang": "fr",
        "client_name": "Léman Pharma Distribution SAS",
        "sender": {"name": "LÉMAN PHARMA DISTRIBUTION SAS",
                   "lines": ["ArchParc – ActiTech 4", "60 Avenue Marie Curie", "CS 40218 – 74160 Archamps"],
                   "contact": "M. Stéphane Ruault", "tel": "+33 4 50 95 09 04"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "2026-22", "order_date": "21.04.2026",
        "requested_delivery_date": "March 2027", "currency": "EUR",
        "notes": "Moyen d'expédition : PORTEUR avec HAYON avec transpalette. Merci de respecter le délai.",
        "lines": [L("OSTENIL PLUS 1 - EU-WEST", "1013", 20, 0)],
        "outcome": "pass",
    },
    # 23 — Malaysia (DCH Auriga) — clean modern PO. PASS
    {
        "source": "malaysia.pdf", "out": "malaysia", "skin": "modern", "lang": "en",
        "client_name": "Selatan Vision Sdn Bhd",
        "sender": {"name": "SELATAN VISION SDN BHD",
                   "lines": ["Lot 6, Persiaran Perusahaan", "Seksyen 23, 40300 Shah Alam", "Selangor, Malaysia"],
                   "contact": "Elaine Sia", "tel": "603-2856 1122"},
        "recipient": TRB_INT_CAROUGE,
        "partner_reference": "TRBM-PO-26014", "order_date": "10.07.2026",
        "requested_delivery_date": "October 2026", "currency": "EUR",
        "notes": "Shelf life at least 24 months upon receipt (except sample pack).",
        "lines": [
            L("VISMED 20 - N", "0687", 20, 1),
            L("VISMED 60 - N", "0846", 3, 2),
            L("VISMED MULTI 10 - N (INT) std", "1083", 18, 3),
            L("VISMED GEL 20 - N", "0899", 14, 4),
            L("VISMED GEL MULTI 10 - N (INT)", "1255", 6, 5),
            L("VISMED 5 - N", "1658", 11, 6),
            L("VISMED GEL 5 - N", "1659", 8, 7),
        ],
        "outcome": "pass",
    },
    # 24 — Dekhon (PK) — invoice/order form. PASS
    {
        "source": "dekhon.pdf", "out": "dekhon", "skin": "invoice", "lang": "en",
        "client_name": "Indus Crescent Pharma (Pvt) Ltd",
        "sender": {"name": "INDUS CRESCENT PHARMA (PVT) LTD",
                   "lines": ["11-C, Old FCC Ferozpur Road", "Lahore", "Pakistan"],
                   "contact": "Muhammad Ali", "tel": "+92 42 3571 6395"},
        "recipient": TRB_INT,
        "partner_reference": "OF-2026-6", "order_date": "09.06.2026",
        "requested_delivery_date": "15.12.2026", "currency": "EUR",
        "notes": "Shipping term: EX WORKS. 90 days from invoice date.",
        "lines": [
            L("VISMED MULTI 10 - N (INT) std", "1083", 28, 8),
            L("VISMED GEL MULTI 10 - N (INT)", "1255", 15, 9),
        ],
        "outcome": "pass",
    },
    # 25 — Propharma (UAE) — invoice. PASS
    {
        "source": "propharma.pdf", "out": "propharma", "skin": "invoice", "lang": "en",
        "client_name": "Gulf Meridian Medical Supplies L.L.C.",
        "sender": {"name": "GULF MERIDIAN MEDICAL SUPPLIES L.L.C.",
                   "lines": ["Al Ain Building M-35, Mussaffah", "Abu Dhabi, P.O. Box 47612", "United Arab Emirates"],
                   "contact": "Procurement", "tel": "+971 2 6734781"},
        "recipient": TRB_INT,
        "partner_reference": "POR-13008", "order_date": "01.10.2025",
        "requested_delivery_date": "October 2025", "currency": "USD",
        "notes": "100% Advance payment. Non-hazardous shipment. Please label properly.",
        "lines": [
            L("OSTENIL 1 - EU-WEST", "0587", 21, 10),
            L("OSTENIL PLUS 1 - EU-WEST", "1013", 12, 11),
            L("OSTENIL TENDON 1 - EU-WEST", "1203", 5, 12),
        ],
        "outcome": "pass",
    },
]


def main():
    # Attribution des codes client 7 chiffres (90000xx), uniques et stables
    for i, o in enumerate(ORDERS, start=1):
        o["customer_code"] = f"900{i:04d}"      # 9000001 .. 9000025 (7 chiffres)
        o.setdefault("intruder_index", None)

    # Sanity : codes uniques, SKU 4 chiffres, qty 1..30, outcomes valides
    codes = [o["customer_code"] for o in ORDERS]
    assert len(codes) == len(set(codes)), "codes client non uniques"
    for o in ORDERS:
        assert len(o["customer_code"]) == 7 and o["customer_code"].isdigit()
        assert o["outcome"] in ("pass", "fail_client", "fail_product")
        for ln in o["lines"]:
            assert len(ln["sku"]) == 4 and ln["sku"].isdigit(), (o["out"], ln["sku"])
            assert 1 <= ln["qty"] <= 30, (o["out"], ln["qty"])
        if o["outcome"] == "fail_product":
            assert o["intruder_index"] is not None and 0 <= o["intruder_index"] < len(o["lines"])

    out = os.path.join(HERE, "faked_orders.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(ORDERS, f, ensure_ascii=False, indent=2)

    n_pass = sum(o["outcome"] == "pass" for o in ORDERS)
    n_fc = sum(o["outcome"] == "fail_client" for o in ORDERS)
    n_fp = sum(o["outcome"] == "fail_product" for o in ORDERS)
    print(f"écrit {out}")
    print(f"{len(ORDERS)} commandes : {n_pass} pass · {n_fc} fail_client · {n_fp} fail_product")


if __name__ == "__main__":
    main()

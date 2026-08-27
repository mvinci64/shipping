#!/usr/bin/env python3
"""
VISCOTTA — Prototipo Fase 1: cartonizzazione → pesi → etichette PDF → bozza DHL
==============================================================================
Uso:
    python cartonize.py ordini.csv [-o out/]

Input:  CSV con colonne  order_number, cliente, data_consegna, sku, qta
        (è il formato dell'export "raw" della Q6 di Metabase, o un estratto
         qualunque della lista prenotazioni)

Output in out/:
    cartonizzazione.json          composizione scatoloni per ordine (con pesi)
    etichette_colli_<ordine>.pdf  un'etichetta per ogni collo WP50/WP40 (lotto+qtà) —
                                   quella che conta ai fini di tracciabilità
    etichette_<ordine>.pdf        un'etichetta 100×150 mm per scatolone (riepilogo
                                   interno, NON sostituisce l'etichetta del corriere)
    dhl_draft_<ordine>.json       payload MyDHL API pronto per la validazione

Regole (censimento 26/08):
    scatolone VISCOTTA = 6 posti; WP50 = 2 posti; WP40 = 1 posto
    ottimizzazione: prima WP50 pieni, resto in WP40;
    i prodotti non censiti vanno segnalati sull'ultimo scatolone.
"""
import csv, json, math, sys, argparse
from pathlib import Path
from collections import defaultdict

# ----------------------------------------------------------------------------
# ANAGRAFICA CONFEZIONI (censimento 26/08) — specchio di prodotto_confezione.
# peso_g: peso della scatola interna piena (tara inclusa).
# fonte 'censimento' = pesata dichiarata; 'derivato' = grammatura SKU + tara,
# DA VERIFICARE con bilancia prima dell'uso in etichetta legale.
# ----------------------------------------------------------------------------
TARA_SCATOLONE_G = 250        # pesato 27/08/2026
POSTI_SCATOLONE = 6           # 6 posti WP40; 1 WP50 = 2 posti
POSTI = {"WP50": 2, "WP40": 1}

CONFEZIONI = {
    # sku: {formato: (pezzi, peso_g, fonte)}
    "CHMS50":    {"WP50": (24, 1400, "derivato"),  "WP40": (12,  750, "derivato")},
    "GRM100":    {"WP50": (24, 2600, "derivato"),  "WP40": (12, 1350, "derivato")},
    "CANTS100":  {"WP50": (24, 2600, "derivato"),  "WP40": (12, 1350, "derivato")},
    "CMEN080":   {"WP50": (24, 2120, "derivato"),  "WP40": (12, 1110, "derivato")},
    "MCIOC080":  {"WP50": (24, 2120, "derivato"),  "WP40": (12, 1110, "derivato")},
    "MSAL080":   {"WP50": (24, 2120, "derivato"),  "WP40": (12, 1110, "derivato")},
    "TCAP075":   {"WP50": (12, 1100, "derivato"),  "WP40": (6,   600, "derivato")},
    "CANT200":   {"WP50": (12, 2850, "censimento"),"WP40": (6,  1500, "censimento")},
    "BRUT150":   {"WP50": (12, 2250, "censimento"),"WP40": (6,  1200, "censimento")},
    "VP08BUST":  {"WP50": (12, 2250, "censimento"),"WP40": (6,  1200, "censimento")},
    "BOXOV":     {                                 "WP40": (6,  1450, "censimento")},
    "SCAT20V08": {                                 "WP40": (6,  1450, "censimento")},
    # scatole regalo/Natale (6/WP40, 1.100 g conf.5 — SKU da confermare):
    # "SCATR05A":  {"WP40": (6, 1100, "censimento")},
}


def cartonize_line(sku: str, qta: int):
    """Riga d'ordine → lista di scatole interne [(formato, pezzi, peso_g)]."""
    conf = CONFEZIONI.get(sku)
    if conf is None:
        return None                      # non censito
    boxes = []
    resto = qta
    if "WP50" in conf:
        pezzi50, peso50, _ = conf["WP50"]
        n50 = resto // pezzi50
        boxes += [("WP50", pezzi50, peso50)] * n50
        resto -= n50 * pezzi50
    pezzi40, peso40, _ = conf["WP40"]
    n40 = math.ceil(resto / pezzi40) if resto else 0
    # nota: l'ultima WP40 può essere parziale — peso proporzionale ai pezzi
    for i in range(n40):
        pezzi_in_box = min(pezzi40, resto)
        peso = peso40 if pezzi_in_box == pezzi40 else round(150 + (peso40 - 150) * pezzi_in_box / pezzi40)
        boxes.append(("WP40", pezzi_in_box, peso))
        resto -= pezzi_in_box
    return boxes


def pack_cartons(boxes):
    """Scatole interne → scatoloni (first-fit, WP50 prima). Ogni scatolone:
    {posti_usati, contenuto: [(formato, sku, pezzi, peso_g)], peso_g}"""
    cartons = []
    for fmt, sku, pezzi, peso in sorted(boxes, key=lambda b: -POSTI[b[0]]):
        posti = POSTI[fmt]
        target = next((c for c in cartons if c["posti_usati"] + posti <= POSTI_SCATOLONE), None)
        if target is None:
            target = {"posti_usati": 0, "contenuto": [], "peso_g": TARA_SCATOLONE_G}
            cartons.append(target)
        target["posti_usati"] += posti
        target["contenuto"].append({"formato": fmt, "sku": sku, "pezzi": pezzi, "peso_g": peso})
        target["peso_g"] += peso
    return cartons


def cartonize_order(rows):
    """Righe di un ordine → risultato completo."""
    boxes, non_censiti = [], []
    for r in rows:
        sku, qta = r["sku"].strip(), int(float(r["qta"]))
        line_boxes = cartonize_line(sku, qta)
        if line_boxes is None:
            non_censiti.append({"sku": sku, "qta": qta})
        else:
            boxes += [(fmt, sku, pezzi, peso) for fmt, pezzi, peso in line_boxes]
    cartons = pack_cartons(boxes)
    return {
        "scatoloni": cartons,
        "n_scatoloni": len(cartons),
        "posti_liberi_ultimo": (POSTI_SCATOLONE - cartons[-1]["posti_usati"]) if cartons else 0,
        "peso_totale_kg": round(sum(c["peso_g"] for c in cartons) / 1000, 2),
        "non_censiti": non_censiti,
    }


# ----------------------------------------------------------------------------
# ETICHETTE COLLO INTERNO — una per ogni scatola WP50/WP40, con lotto e
# quantità. Questa è l'etichetta che conta ai fini di tracciabilità: va
# applicata sulla scatola interna PRIMA di chiuderla nello scatolone.
# In Fase 1 lotto/scadenza sono placeholder: il dato reale arriva dal
# miniMRP e va stampato a fine linea (Fase 2), non calcolato qui.
# ----------------------------------------------------------------------------
def make_inner_labels(order, result, out_path: Path):
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import code128

    W, H = 60 * mm, 40 * mm   # formato ridotto, pensato per la scatola interna
    c = canvas.Canvas(str(out_path), pagesize=(W, H))
    colli = [item for carton in result["scatoloni"] for item in carton["contenuto"]]
    n_tot = len(colli)
    for i, item in enumerate(colli, 1):
        y = H - 6 * mm
        c.setFont("Helvetica-Bold", 11); c.drawCentredString(W / 2, y, "VISCOTTA")
        y -= 5 * mm
        c.setFont("Helvetica-Bold", 9)
        c.drawString(4 * mm, y, f"{item['sku']}  ({item['formato']})")
        y -= 4.5 * mm
        c.setFont("Helvetica", 8)
        c.drawString(4 * mm, y, f"Quantità: {item['pezzi']} pz")
        y -= 4.5 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawString(4 * mm, y, "Lotto: __________  Scad.: __________")
        y -= 5 * mm
        c.setFont("Helvetica", 6)
        c.drawString(4 * mm, y, f"Ordine {order['order_number']} — {order['cliente'][:24]}")
        bc = code128.Code128(f"{order['order_number']}-{i:02d}", barHeight=6 * mm, barWidth=0.2 * mm)
        bc.drawOn(c, (W - bc.width) / 2, 2 * mm)
        c.showPage()
    c.save()


# ----------------------------------------------------------------------------
# ETICHETTA SCATOLONE — 100×150 mm, una per scatolone. Riepilogo interno di
# cosa contiene il collo di spedizione: NON è l'etichetta ufficiale del
# corriere (quella la emette DHL/BRT su quel collo alla creazione della
# spedizione) e non sostituisce le etichette dei singoli WP50/WP40.
# ----------------------------------------------------------------------------
def make_labels(order, result, out_path: Path):
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import code128

    W, H = 100 * mm, 150 * mm
    c = canvas.Canvas(str(out_path), pagesize=(W, H))
    n_tot = result["n_scatoloni"]
    for i, carton in enumerate(result["scatoloni"], 1):
        y = H - 12 * mm
        c.setFont("Helvetica-Bold", 20); c.drawCentredString(W / 2, y, "VISCOTTA")
        y -= 6 * mm
        c.setFont("Helvetica", 8); c.drawCentredString(W / 2, y, "Prodotti da forno artigianali")
        y -= 3 * mm; c.line(6 * mm, y, W - 6 * mm, y); y -= 8 * mm
        c.setFont("Helvetica-Bold", 12); c.drawString(8 * mm, y, order["cliente"][:38])
        y -= 6 * mm
        c.setFont("Helvetica", 10)
        c.drawString(8 * mm, y, f"Ordine {order['order_number']} — consegna {order['data_consegna']}")
        y -= 9 * mm
        c.setFont("Helvetica-Bold", 11); c.drawString(8 * mm, y, "Contenuto:")
        y -= 6 * mm; c.setFont("Helvetica", 9)
        for item in carton["contenuto"]:
            c.drawString(10 * mm, y, f"1× {item['formato']}  {item['sku']}  ({item['pezzi']} pz)")
            c.drawRightString(W - 8 * mm, y, f"{item['peso_g'] / 1000:.2f} kg")
            y -= 5 * mm
        if i == n_tot and result["non_censiti"]:
            y -= 2 * mm
            c.setFont("Helvetica-Oblique", 8)
            for nc in result["non_censiti"]:
                c.drawString(10 * mm, y, f"+ {nc['qta']}× {nc['sku']} (da sistemare a mano)")
                y -= 4 * mm
        y -= 4 * mm; c.line(6 * mm, y, W - 6 * mm, y); y -= 8 * mm
        c.setFont("Helvetica-Bold", 13)
        c.drawString(8 * mm, y, f"Peso lordo: {carton['peso_g'] / 1000:.2f} kg")
        c.drawRightString(W - 8 * mm, y, f"Collo {i}/{n_tot}")
        y -= 7 * mm
        c.setFont("Helvetica", 7)
        c.drawString(8 * mm, y, "Riepilogo interno — non sostituisce l'etichetta del corriere")
        bc = code128.Code128(f"{order['order_number']}-{i:02d}", barHeight=13 * mm, barWidth=0.33 * mm)
        bc.drawOn(c, (W - bc.width) / 2, 8 * mm)
        c.showPage()
    c.save()


# ----------------------------------------------------------------------------
# BOZZA DHL — payload MyDHL API (POST /shipments), un package per scatolone.
# Da usare prima in modalità VALIDAZIONE (senza emissione etichetta AWB):
# vedere MyDHL API "Shipment data validation flow". Credenziali e indirizzi
# vanno completati con i dati del contratto DHL Express.
# ----------------------------------------------------------------------------
DHL_DIMS_SCATOLONE_CM = {"length": 40, "width": 30, "height": 30}   # DA MISURARE

def make_dhl_draft(order, result):
    return {
        "plannedShippingDateAndTime": f"{order['data_consegna']}T09:00:00 GMT+02:00",
        "pickup": {"isRequested": False},
        "productCode": "N",                       # domestico IT; estero: P/U ecc.
        "accounts": [{"typeCode": "shipper", "number": "<<DHL_ACCOUNT_NUMBER>>"}],
        "customerDetails": {
            "shipperDetails": {
                "postalAddress": {"postalCode": "<<CAP>>", "cityName": "<<CITTA>>",
                                  "countryCode": "IT", "addressLine1": "<<INDIRIZZO VISCOTTA>>"},
                "contactInformation": {"companyName": "VISCOTTA",
                                       "fullName": "Spedizioni VISCOTTA",
                                       "phone": "<<TELEFONO>>", "email": "<<EMAIL>>"},
            },
            "receiverDetails": {
                "postalAddress": {"postalCode": "<<CAP_CLIENTE>>", "cityName": "<<CITTA_CLIENTE>>",
                                  "countryCode": "IT", "addressLine1": "<<INDIRIZZO_CLIENTE>>"},
                "contactInformation": {"companyName": order["cliente"],
                                       "fullName": order["cliente"],
                                       "phone": "<<TELEFONO_CLIENTE>>", "email": "<<EMAIL_CLIENTE>>"},
            },
        },
        "content": {
            "packages": [
                {"customerReferences": [{"value": f"{order['order_number']}-{i:02d}"}],
                 "weight": round(c["peso_g"] / 1000, 2),
                 "dimensions": DHL_DIMS_SCATOLONE_CM}
                for i, c in enumerate(result["scatoloni"], 1)
            ],
            "isCustomsDeclarable": False,
            "description": f"Prodotti da forno — ordine {order['order_number']}",
            "incoterm": "DAP",
            "unitOfMeasurement": "metric",
        },
        "customerReferences": [{"value": order["order_number"]}],
    }


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file")
    ap.add_argument("-o", "--out", default="out")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    orders = defaultdict(list)
    with open(args.csv_file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            orders[row["order_number"]].append(row)

    summary = {}
    for order_number, rows in orders.items():
        order = {"order_number": order_number,
                 "cliente": rows[0].get("cliente", ""),
                 "data_consegna": rows[0].get("data_consegna", "")}
        result = cartonize_order(rows)
        summary[order_number] = {**order, **result}
        if result["n_scatoloni"]:
            make_inner_labels(order, result, out / f"etichette_colli_{order_number}.pdf")
            make_labels(order, result, out / f"etichette_{order_number}.pdf")
            (out / f"dhl_draft_{order_number}.json").write_text(
                json.dumps(make_dhl_draft(order, result), indent=2, ensure_ascii=False))
        print(f"{order_number}  {order['cliente'][:30]:30s}  "
              f"scatoloni={result['n_scatoloni']}  peso={result['peso_totale_kg']} kg  "
              f"posti liberi={result['posti_liberi_ultimo']}  "
              f"non censiti={len(result['non_censiti'])}")

    (out / "cartonizzazione.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nOutput in {out}/")


if __name__ == "__main__":
    main()

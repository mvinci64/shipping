"""Logica di cartonizzazione — porting da prototype/cartonize.py.

Regole (censimento 26/08): scatolone VISCOTTA = 6 posti; WP50 = 2 posti;
WP40 = 1 posto. Ottimizzazione: prima WP50 pieni, resto in WP40; i prodotti
non censiti vengono segnalati come tali.
"""
import math

TARA_SCATOLONE_G = 400        # DA PESARE
POSTI_SCATOLONE = 6
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
}


def cartonize_line(sku: str, qta: int):
    """Riga d'ordine → lista di scatole interne [(formato, pezzi, peso_g)]."""
    conf = CONFEZIONI.get(sku)
    if conf is None:
        return None
    boxes = []
    resto = qta
    if "WP50" in conf:
        pezzi50, peso50, _ = conf["WP50"]
        n50 = resto // pezzi50
        boxes += [("WP50", pezzi50, peso50)] * n50
        resto -= n50 * pezzi50
    pezzi40, peso40, _ = conf["WP40"]
    n40 = math.ceil(resto / pezzi40) if resto else 0
    for i in range(n40):
        pezzi_in_box = min(pezzi40, resto)
        peso = peso40 if pezzi_in_box == pezzi40 else round(150 + (peso40 - 150) * pezzi_in_box / pezzi40)
        boxes.append(("WP40", pezzi_in_box, peso))
        resto -= pezzi_in_box
    return boxes


def pack_cartons(boxes):
    """Scatole interne → scatoloni (first-fit, WP50 prima)."""
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
    """Righe di un ordine (dict con sku, qta) → risultato completo."""
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

"""Logica di cartonizzazione — porting da prototype/cartonize.py.

Regole (censimento 26/08): scatolone VISCOTTA = 6 posti; WP50 = 2 posti;
WP40 = 1 posto. Ottimizzazione: prima WP50 pieni, resto in WP40; i prodotti
non censiti vengono segnalati come tali.
"""
import math

TARA_SCATOLONE_G = 500        # forfait — confermato dall'utente 04/09/2026, sostituisce la pesata 250g del 27/08

POSTI_SCATOLONE = 6
POSTI = {"WP50": 2, "WP40": 1}

# Tara della scatola interna vuota (censimento 26/08).
TARA_COLLO_G = {"WP50": 200, "WP40": 150}

# Sovrappeso confezionamento per singolo pezzo di prodotto (nastro/etichetta
# sulla confezione individuale) — regola confermata dall'utente 04/09/2026.
SOVRAPPESO_CONFEZIONE_G = 6

# Grammatura netta per pezzo — per gli SKU standard è il numero nel codice
# (es. CHMS50 -> 50g); per VP08BUST/BOXOV/SCAT20V08, dove il codice non lo
# esprime, il valore è stato confermato a parte dall'utente 04/09/2026.
GRAMMATURA_G = {
    "CHMS50": 50, "GRM100": 100, "CANTS100": 100, "CMEN080": 80, "MCIOC080": 80, "MSAL080": 80,
    "MPEL150": 150, "MSGU150": 150, "MPEL200": 200, "MSGU200": 200,
    "TCAP075": 75, "CANT200": 200, "BRUT150": 150,
    "VP08BUST": 160, "BOXOV": 150, "SCAT20V08": 160,
}


def _peso_collo_g(sku: str, formato: str, pezzi: int) -> int:
    """peso = grammatura netta * pezzi + sovrappeso confezione * pezzi + tara scatola interna."""
    return pezzi * (GRAMMATURA_G[sku] + SOVRAPPESO_CONFEZIONE_G) + TARA_COLLO_G[formato]


# sku: {formato: pezzi} — quanti pezzi entrano in ogni formato di scatola interna (censimento 26/08).
PEZZI_PER_COLLO = {
    "CHMS50":    {"WP50": 24, "WP40": 12},
    "GRM100":    {"WP50": 24, "WP40": 12},
    "CANTS100":  {"WP50": 24, "WP40": 12},
    "CMEN080":   {"WP50": 24, "WP40": 12},
    "MCIOC080":  {"WP50": 24, "WP40": 12},
    "MSAL080":   {"WP50": 24, "WP40": 12},
    "MPEL150":   {"WP50": 24, "WP40": 12},
    "MSGU150":   {"WP50": 24, "WP40": 12},
    "MPEL200":   {"WP50": 24, "WP40": 12},
    "MSGU200":   {"WP50": 24, "WP40": 12},
    "TCAP075":   {"WP50": 12, "WP40": 6},
    "CANT200":   {"WP50": 12, "WP40": 6},
    "BRUT150":   {"WP50": 12, "WP40": 6},
    "VP08BUST":  {"WP50": 12, "WP40": 6},
    "BOXOV":     {"WP40": 6},
    "SCAT20V08": {"WP40": 6},
}

# sku: {formato: (pezzi, peso_g)} — peso ricalcolato dalla formula sopra,
# non più un numero pesato/derivato a mano per ogni riga.
CONFEZIONI = {
    sku: {fmt: (pz, _peso_collo_g(sku, fmt, pz)) for fmt, pz in formati.items()}
    for sku, formati in PEZZI_PER_COLLO.items()
}


def cartonize_line(sku: str, qta: int):
    """Riga d'ordine → lista di scatole interne [(formato, pezzi, peso_g)]."""
    conf = CONFEZIONI.get(sku)
    if conf is None:
        return None
    boxes = []
    resto = qta
    if "WP50" in conf:
        pezzi50, peso50 = conf["WP50"]
        n50 = resto // pezzi50
        boxes += [("WP50", pezzi50, peso50)] * n50
        resto -= n50 * pezzi50
    pezzi40, peso40 = conf["WP40"]
    tara40 = TARA_COLLO_G["WP40"]
    n40 = math.ceil(resto / pezzi40) if resto else 0
    for i in range(n40):
        pezzi_in_box = min(pezzi40, resto)
        peso = peso40 if pezzi_in_box == pezzi40 else round(tara40 + (peso40 - tara40) * pezzi_in_box / pezzi40)
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

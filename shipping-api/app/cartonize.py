"""Logica di cartonizzazione — porting da prototype/cartonize.py.

Regole (censimento 26/08): scatolone VISCOTTA = 6 posti; WP50 = 2 posti;
WP40 = 1 posto. Ottimizzazione: prima WP50 pieni, resto in WP40; i prodotti
non censiti vengono segnalati come tali.
"""
import math

TARA_SCATOLONE_G = 900        # pesata reale su ORD-20260721-4387 (07/09/2026) — sostituisce il forfait 500g del 04/09
CARTA_RIEMPIMENTO_G = 500      # media di carta da riempimento per scatolone — aggiunta 07/09/2026, prima non contava

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
# MSAL1KG/CHMS1KG/CANTS1KG/GRM1KG (nuovi formati da 1kg, ciascuno diviso in
# buste da 500g) — censiti dall'utente 09/09/2026, primo ordine reale
# ORD-20260908-9232.
GRAMMATURA_G = {
    "CHMS50": 50, "GRM100": 100, "CANTS100": 100, "CMEN080": 80, "MCIOC080": 80, "MSAL080": 80,
    "MPEL150": 150, "MSGU150": 150, "MPEL200": 200, "MSGU200": 200,
    "TCAP075": 75, "CANT200": 200, "BRUT150": 150,
    "VP08BUST": 160, "BOXOV": 150, "SCAT20V08": 160,
    "MSAL1KG": 1000, "CHMS1KG": 1000, "CANTS1KG": 1000, "GRM1KG": 1000,
    "TCAP200SC": 200,
    # Scatole regalo/Natale (SKU confermati 12/09/2026, prima "da confermare"
    # — vedi valutazione-cartonizzazione.md). Qui "grammatura" è il peso
    # dell'intera confezione (non del singolo pasticcino: queste SKU sono
    # vendute come scatola assortita, ogni unità ordinata = una scatola),
    # dato dall'utente: 100g le scatole da 5 pezzi, 200g quelle da 10,
    # indipendentemente da regalo/natalizia; Marunetta e Spiritose pesate
    # a parte (box da 6, ricette diverse).
    "SCATR05A": 100, "SCATRN05A": 100,
    "SCATR10A": 200, "SCATRN10A": 200,
    "SCATM06M": 180,
    "SCATM06SR": 150, "SCATM06SA": 150,
    # Pasta di mandorla singola, stesso biscotto delle scatole/buste
    # assortite (20 g/pz) — censita 14/09/2026 per il primo collo misto
    # reale, ORD-20260505-4944 (50+50 VP01/VP06 e VP05/VP04 in due WP40).
    "VP01": 20, "VP02": 20, "VP04": 20, "VP05": 20, "VP06": 20,
}

# SKU "sfusi": niente scatola interna WP40/WP50, i pezzi riempiono
# direttamente lo spazio residuo dello scatolone (nessuna tara scatola
# interna nel peso, nessun posto occupato nello scatolone). L'etichetta
# collo per questi SKU mostra solo la quantità, senza formato — deciso
# dall'utente 11/09/2026 per TCAP200SC, esteso alle scatole regalo/Natale
# il 12/09/2026. Primi ordini reali: ORD-20260908-6587, ORD-20260505-4944.
SFUSO_SKUS = {
    "TCAP200SC",
    "SCATR05A", "SCATR10A", "SCATRN05A", "SCATRN10A",
    "SCATM06M", "SCATM06SR", "SCATM06SA",
}


def _peso_collo_g(sku: str, formato: str, pezzi: int) -> int:
    """peso = grammatura netta * pezzi + sovrappeso confezione * pezzi + tara scatola interna."""
    return pezzi * (GRAMMATURA_G[sku] + SOVRAPPESO_CONFEZIONE_G) + TARA_COLLO_G[formato]


def _peso_sfuso_g(sku: str, pezzi: int) -> int:
    """peso = grammatura netta * pezzi + sovrappeso confezione * pezzi — niente tara, non c'è scatola interna."""
    return pezzi * (GRAMMATURA_G[sku] + SOVRAPPESO_CONFEZIONE_G)


# sku: {formato: pezzi} — quanti pezzi entrano in ogni formato di scatola interna (censimento 26/08).
PEZZI_PER_COLLO = {
    "CHMS50":    {"WP50": 24, "WP40": 12},
    "GRM100":    {"WP50": 24, "WP40": 12},
    "CANTS100":  {"WP50": 24, "WP40": 12},
    "CMEN080":   {"WP50": 24, "WP40": 12},
    "MCIOC080":  {"WP50": 24, "WP40": 12},
    # MSAL080 entra più fitto degli altri prodotti da 80g: capacità propria,
    # non il forfait 24/12 condiviso col resto del gruppo — confermato
    # dall'utente 09/09/2026 (36 pezzi pieni un WP50, 24 pieni un WP40).
    "MSAL080":   {"WP50": 36, "WP40": 24},
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
    "MSAL1KG":   {"WP50": 2, "WP40": 1},
    "CHMS1KG":   {"WP50": 2, "WP40": 1},
    "CANTS1KG":  {"WP50": 2, "WP40": 1},
    "GRM1KG":    {"WP50": 2, "WP40": 1},
}

# sku: {formato: (pezzi, peso_g)} — peso ricalcolato dalla formula sopra,
# non più un numero pesato/derivato a mano per ogni riga.
CONFEZIONI = {
    sku: {fmt: (pz, _peso_collo_g(sku, fmt, pz)) for fmt, pz in formati.items()}
    for sku, formati in PEZZI_PER_COLLO.items()
}


def cartonize_line(sku: str, qta: int):
    """Riga d'ordine → lista di scatole interne [(formato, pezzi, peso_g)].
    Per gli SKU sfusi (vedi SFUSO_SKUS) formato è None: niente scatola
    interna, un'unica riga con tutti i pezzi dell'ordine."""
    if sku in SFUSO_SKUS:
        return [(None, qta, _peso_sfuso_g(sku, qta))]
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
    """Scatole interne → scatoloni (first-fit, WP50 prima). Gli SKU sfusi
    (fmt None) non occupano posti: riempiono lo scatolone corrente dopo
    aver piazzato le scatole interne WP50/WP40. boxes è una lista di
    4-tuple (fmt, sku, pezzi, peso) o 5-tuple (fmt, sku, pezzi, peso,
    componenti) per i colli misti (sku è None in quel caso — vedi
    collo_misto_box)."""
    cartons = []
    for box in sorted(boxes, key=lambda b: -POSTI.get(b[0], 0)):
        fmt, sku, pezzi, peso = box[:4]
        componenti = box[4] if len(box) > 4 else None
        posti = POSTI.get(fmt, 0)
        target = next((c for c in cartons if c["posti_usati"] + posti <= POSTI_SCATOLONE), None)
        if target is None:
            target = {"posti_usati": 0, "contenuto": [], "peso_g": TARA_SCATOLONE_G + CARTA_RIEMPIMENTO_G}
            cartons.append(target)
        target["posti_usati"] += posti
        entry = {"formato": fmt, "sku": sku, "pezzi": pezzi, "peso_g": peso}
        if componenti:
            entry["componenti"] = componenti
        target["contenuto"].append(entry)
        target["peso_g"] += peso
    return cartons


def collo_misto_box(formato: str, componenti: list[dict]) -> tuple:
    """Costruisce un box 'misto' pronto per pack_cartons: più SKU nella
    stessa scatola interna, peso somma dei componenti (stessa formula di
    _peso_collo_g). componenti: [{"sku": ..., "pezzi": ...}, ...]. Ogni sku
    deve avere un peso noto in GRAMMATURA_G — KeyError esplicito altrimenti
    (niente peso indovinato per una spedizione DHL reale)."""
    peso = sum(c["pezzi"] * (GRAMMATURA_G[c["sku"]] + SOVRAPPESO_CONFEZIONE_G) for c in componenti)
    peso += TARA_COLLO_G[formato]
    pezzi_totali = sum(c["pezzi"] for c in componenti)
    return (formato, None, pezzi_totali, peso, componenti)


def cartonize_order(rows, colli_misti: list[dict] | None = None):
    """Righe di un ordine (dict con sku, qta) → risultato completo.
    colli_misti (opzionale): colli WP40/WP50 con più SKU decisi a mano
    dall'operatore (vedi sql/colli_misti_manuali.sql), ciascuno
    {"formato": ..., "componenti": [{"sku": ..., "pezzi": ...}, ...]}. Le
    quantità già assegnate a un collo misto vengono sottratte dalle righe
    prima della cartonizzazione automatica, così non finiscono duplicate
    né segnalate come non censite."""
    colli_misti = colli_misti or []
    consumo: dict[str, int] = {}
    for cm in colli_misti:
        for comp in cm["componenti"]:
            consumo[comp["sku"]] = consumo.get(comp["sku"], 0) + comp["pezzi"]

    disponibile: dict[str, int] = {}
    for r in rows:
        sku = r["sku"].strip()
        disponibile[sku] = disponibile.get(sku, 0) + int(float(r["qta"]))
    for sku, qta_richiesta in consumo.items():
        if qta_richiesta > disponibile.get(sku, 0):
            raise ValueError(
                f"Collo misto: {sku} richiede {qta_richiesta} pezzi ma l'ordine ne ha solo {disponibile.get(sku, 0)}"
            )

    boxes, non_censiti = [], []
    consumo_rimanente = dict(consumo)
    for r in rows:
        sku, qta = r["sku"].strip(), int(float(r["qta"]))
        # se lo stesso sku è su più righe, il prelievo si spalma tra le
        # righe nell'ordine in cui compaiono, senza sottrarlo più volte
        prelievo = min(qta, consumo_rimanente.get(sku, 0))
        consumo_rimanente[sku] = consumo_rimanente.get(sku, 0) - prelievo
        qta_residua = qta - prelievo
        if qta_residua <= 0:
            continue
        line_boxes = cartonize_line(sku, qta_residua)
        if line_boxes is None:
            non_censiti.append({"sku": sku, "qta": qta_residua})
        else:
            boxes += [(fmt, sku, pezzi, peso) for fmt, pezzi, peso in line_boxes]

    for cm in colli_misti:
        boxes.append(collo_misto_box(cm["formato"], cm["componenti"]))

    cartons = pack_cartons(boxes)
    return {
        "scatoloni": cartons,
        "n_scatoloni": len(cartons),
        "posti_liberi_ultimo": (POSTI_SCATOLONE - cartons[-1]["posti_usati"]) if cartons else 0,
        "peso_totale_kg": round(sum(c["peso_g"] for c in cartons) / 1000, 2),
        "non_censiti": non_censiti,
    }

"""Etichette collo interno (WP50/WP40) — porting da prototype/cartonize.py.

Una etichetta per ogni scatola interna, con lotto e quantità: è quella che
conta ai fini di tracciabilità (va applicata sulla scatola interna PRIMA di
chiuderla nello scatolone). Lotto/scadenza reali arrivano da
easyfatt.tmovmagazz (ultimo carico per SKU — vedi db.fetch_ultimo_lotto),
non da viscotta.ordini_produzione (miniMRP), che non li ha in campo
strutturato. Senza il dict `lotti` (es. ordini di test via CSV, senza
riscontro in EasyFatt) resta il placeholder da compilare a mano.

Gerarchia visiva decisa col reparto packaging (02/09/2026): cliente e
quantità sono le informazioni che contano per chi fa i colli, quindi in
grande e ben visibili; VISCOTTA e il formato (WP50/WP40) sono un dettaglio,
in piccolo. Il barcode GS1-128 (GTIN da easyfatt.tarticoli.codbarre, non
censito per tutti gli articoli) resta a fondo etichetta ma ridotto, per non
rubare spazio — con lotto/scadenza quando disponibili (AI(01)+AI(17)+AI(10)),
altrimenti col solo GTIN (AI(01)): serve comunque a identificare il
prodotto quando si stampa in anticipo, prima che tutto l'ordine sia stato
prodotto (mostra_lotto=False, vedi sotto).

NON genera l'etichetta scatolone: quella è un riepilogo interno separato,
e non sostituisce comunque l'etichetta ufficiale del corriere (DHL/BRT).
"""
import io


def _payload_gs1_128(gtin13: str, lotto: str, scadenza_iso: str) -> str:
    """AI(01) GTIN-14 + AI(17) scadenza YYMMDD + AI(10) lotto (ultimo AI,
    lunghezza variabile: non serve separatore FNC1 dopo). \xf1 = FNC1."""
    gtin14 = gtin13.rjust(14, "0")
    yy, mm, dd = scadenza_iso.split("-")
    yymmdd = yy[2:] + mm + dd
    return f"\xf101{gtin14}17{yymmdd}10{lotto}"


def _payload_gs1_solo_gtin(gtin13: str) -> str:
    """Solo AI(01) GTIN-14, senza lotto/scadenza — per le etichette stampate
    in anticipo (mostra_lotto=False), quando serve identificare il prodotto
    ma lotto/scadenza non sono ancora affidabili per tutto l'ordine."""
    return f"\xf101{gtin13.rjust(14, '0')}"


def _tronca_a_larghezza(c, testo: str, font: str, size: float, larghezza_max: float) -> str:
    """Accorcia testo con '…' finché non entra in larghezza_max, al size dato."""
    if c.stringWidth(testo, font, size) <= larghezza_max:
        return testo
    while testo and c.stringWidth(testo + "…", font, size) > larghezza_max:
        testo = testo[:-1]
    return testo + "…"


def _a_capo(c, testo: str, font: str, size: float, larghezza_max: float, righe_max: int) -> list[str]:
    """Spezza testo su più righe (word-wrap) invece di troncarlo subito — c'è
    spazio sotto per un secondo rigo. Oltre righe_max, l'ultimo rigo viene
    troncato con '…' come in _tronca_a_larghezza."""
    parole = testo.split()
    righe: list[str] = []
    corrente = ""
    i = 0
    while i < len(parole):
        parola = parole[i]
        prova = f"{corrente} {parola}".strip()
        if c.stringWidth(prova, font, size) <= larghezza_max:
            corrente = prova
            i += 1
            continue
        if not corrente:
            corrente = parola  # parola singola più larga della riga: forzata comunque
            i += 1
        righe.append(corrente)
        corrente = ""
        if len(righe) == righe_max:
            break
    else:
        if corrente:
            righe.append(corrente)

    if len(righe) == righe_max and i < len(parole):
        resto = " ".join(parole[i:])
        righe[-1] = _tronca_a_larghezza(c, f"{righe[-1]} {resto}", font, size, larghezza_max)
    return righe or [""]


def make_inner_labels_pdf(
    order_number: str,
    cliente: str,
    result: dict,
    lotti: dict | None = None,
    gtins: dict | None = None,
    nomi_prodotto: dict | None = None,
    mostra_lotto: bool = True,
) -> bytes:
    """mostra_lotto=False: stampa etichette in anticipo, prima che tutti i
    prodotti dell'ordine siano stati prodotti (es. solo il primo della lista
    è uscito dal laboratorio). In quel caso lotto/scadenza/barcode GS1 non
    hanno senso per i prodotti non ancora fatti — vengono omessi del tutto
    per l'intero ordine, non solo per lo SKU mancante, per non dare
    l'impressione che l'informazione manchi solo per errore."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import code128

    buf = io.BytesIO()
    # 15x10 cm orizzontale — formato della stampante etichette non trasparenti
    # di laboratorio.
    W, H = 150 * mm, 100 * mm
    c = canvas.Canvas(buf, pagesize=(W, H))
    margine = 8 * mm
    larghezza_utile = W - 2 * margine
    colli = [item for carton in result["scatoloni"] for item in carton["contenuto"]]
    for item in colli:
        y = H - 8 * mm
        # riga piccola: VISCOTTA a sinistra, ordine a destra
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margine, y, "VISCOTTA")
        c.setFont("Helvetica", 8)
        c.drawRightString(W - margine, y, f"Ordine {order_number}")
        y -= 11 * mm

        # cliente: l'informazione dominante, font grande — a capo su 2 righe
        # se non entra su una sola, invece di troncare (c'è spazio sotto)
        righe_cliente = _a_capo(c, cliente, "Helvetica-Bold", 22, larghezza_utile, righe_max=2)
        c.setFont("Helvetica-Bold", 22)
        for riga in righe_cliente:
            c.drawString(margine, y, riga)
            y -= 8.5 * mm
        y -= 6.5 * mm if len(righe_cliente) == 1 else 0

        # SKU normale, formato (WP50/WP40) piccolo
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margine, y, item["sku"])
        c.setFont("Helvetica", 9)
        c.drawString(margine + c.stringWidth(item["sku"], "Helvetica-Bold", 14) + 2 * mm, y, f"({item['formato']})")
        y -= 8 * mm

        # nome prodotto: a fianco dello SKU, deve essere chiaro a colpo
        # d'occhio cosa contiene il collo — su una sola riga, troncato con
        # '…' se troppo lungo (mai a capo)
        nome_prodotto = (nomi_prodotto or {}).get(item["sku"])
        if nome_prodotto:
            c.setFont("Helvetica-Bold", 15)
            c.drawString(margine, y, _tronca_a_larghezza(c, nome_prodotto, "Helvetica-Bold", 15, larghezza_utile))
        y -= 9.2 * mm

        # quantità: seconda informazione dominante, font grande
        c.setFont("Helvetica-Bold", 26)
        c.drawString(margine, y, f"{item['pezzi']} pz")
        y -= 11 * mm

        gtin = (gtins or {}).get(item["sku"])
        if mostra_lotto:
            c.setFont("Helvetica-Bold", 14)
            lotto = (lotti or {}).get(item["sku"])
            if lotto:
                c.drawString(margine, y, f"Lotto: {lotto['lotto']}   Scad.: {lotto['scadenza']}")
            else:
                c.drawString(margine, y, "Lotto: __________   Scad.: __________")

            if gtin and lotto and lotto.get("scadenza"):
                payload = _payload_gs1_128(gtin, lotto["lotto"], lotto["scadenza"])
                bc = code128.Code128(payload, barHeight=10 * mm, barWidth=0.22 * mm)
                bc.drawOn(c, W - margine - bc.width, 4 * mm)
                c.setFont("Helvetica", 6)
                c.drawRightString(W - margine, 14.5 * mm, f"GTIN {gtin}")
            else:
                c.setFont("Helvetica", 8)
                c.drawRightString(W - margine, 6 * mm, "GTIN non censito")
        elif gtin:
            # solo prodotto, senza lotto/scadenza — barcode GS1 col solo AI(01)
            payload = _payload_gs1_solo_gtin(gtin)
            bc = code128.Code128(payload, barHeight=10 * mm, barWidth=0.22 * mm)
            bc.drawOn(c, W - margine - bc.width, 4 * mm)
            c.setFont("Helvetica", 6)
            c.drawRightString(W - margine, 14.5 * mm, f"GTIN {gtin}")
        c.showPage()
    c.save()
    return buf.getvalue()

"""Etichette collo interno (WP50/WP40) — porting da prototype/cartonize.py.

Una etichetta per ogni scatola interna, con lotto e quantità: è quella che
conta ai fini di tracciabilità (va applicata sulla scatola interna PRIMA di
chiuderla nello scatolone). Lotto/scadenza reali arrivano da
easyfatt.tmovmagazz (ultimo carico per SKU — vedi db.fetch_ultimo_lotto),
non da viscotta.ordini_produzione (miniMRP), che non li ha in campo
strutturato. Senza il dict `lotti` (es. ordini di test via CSV, senza
riscontro in EasyFatt) resta il placeholder da compilare a mano.

Il barcode è GS1-128 standard: AI(01) GTIN-14, AI(17) scadenza (YYMMDD),
AI(10) lotto — GTIN da easyfatt.tarticoli.codbarre (vedi db.fetch_gtin),
non censito per tutti gli articoli. Senza GTIN o lotto non c'è payload GS1
valido: l'etichetta esce senza barcode, solo testo, da completare a mano.

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


def make_inner_labels_pdf(
    order_number: str,
    cliente: str,
    result: dict,
    lotti: dict | None = None,
    gtins: dict | None = None,
) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import code128

    buf = io.BytesIO()
    # 10x15 cm — formato della stampante etichette non trasparenti di laboratorio.
    W, H = 100 * mm, 150 * mm
    c = canvas.Canvas(buf, pagesize=(W, H))
    margine = 8 * mm
    colli = [item for carton in result["scatoloni"] for item in carton["contenuto"]]
    for item in colli:
        y = H - 16 * mm
        c.setFont("Helvetica-Bold", 26); c.drawCentredString(W / 2, y, "VISCOTTA")
        y -= 14 * mm
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margine, y, f"{item['sku']}  ({item['formato']})")
        y -= 11 * mm
        c.setFont("Helvetica", 14)
        c.drawString(margine, y, f"Quantità: {item['pezzi']} pz")
        y -= 12 * mm
        c.setFont("Helvetica-Bold", 15)
        lotto = (lotti or {}).get(item["sku"])
        if lotto:
            c.drawString(margine, y, f"Lotto: {lotto['lotto']}")
            y -= 8 * mm
            c.drawString(margine, y, f"Scad.: {lotto['scadenza']}")
        else:
            c.drawString(margine, y, "Lotto: __________")
            y -= 8 * mm
            c.drawString(margine, y, "Scad.: __________")
        y -= 10 * mm
        c.setFont("Helvetica", 9)
        c.drawString(margine, y, f"Ordine {order_number} — {cliente[:32]}")

        gtin = (gtins or {}).get(item["sku"])
        if gtin and lotto and lotto.get("scadenza"):
            payload = _payload_gs1_128(gtin, lotto["lotto"], lotto["scadenza"])
            bc = code128.Code128(payload, barHeight=22 * mm, barWidth=0.4 * mm)
            bc.drawOn(c, (W - bc.width) / 2, 15 * mm)
            c.setFont("Helvetica", 8)
            c.drawCentredString(W / 2, 10 * mm, f"GTIN {gtin}")
        else:
            c.setFont("Helvetica", 11)
            c.drawCentredString(W / 2, 20 * mm, "GTIN non censito — nessun barcode")
        c.showPage()
    c.save()
    return buf.getvalue()

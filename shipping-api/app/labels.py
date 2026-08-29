"""Etichette collo interno (WP50/WP40) — porting da prototype/cartonize.py.

Una etichetta per ogni scatola interna, con lotto e quantità: è quella che
conta ai fini di tracciabilità (va applicata sulla scatola interna PRIMA di
chiuderla nello scatolone). Lotto/scadenza reali arrivano da
easyfatt.tmovmagazz (ultimo carico per SKU — vedi db.fetch_ultimo_lotto),
non da viscotta.ordini_produzione (miniMRP), che non li ha in campo
strutturato. Senza il dict `lotti` (es. ordini di test via CSV, senza
riscontro in EasyFatt) resta il placeholder da compilare a mano.

NON genera l'etichetta scatolone: quella è un riepilogo interno separato,
e non sostituisce comunque l'etichetta ufficiale del corriere (DHL/BRT).
"""
import io


def make_inner_labels_pdf(order_number: str, cliente: str, result: dict, lotti: dict | None = None) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.graphics.barcode import code128

    buf = io.BytesIO()
    W, H = 60 * mm, 40 * mm
    c = canvas.Canvas(buf, pagesize=(W, H))
    colli = [item for carton in result["scatoloni"] for item in carton["contenuto"]]
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
        lotto = (lotti or {}).get(item["sku"])
        if lotto:
            c.drawString(4 * mm, y, f"Lotto: {lotto['lotto']}  Scad.: {lotto['scadenza']}")
        else:
            c.drawString(4 * mm, y, "Lotto: __________  Scad.: __________")
        y -= 5 * mm
        c.setFont("Helvetica", 6)
        c.drawString(4 * mm, y, f"Ordine {order_number} — {cliente[:24]}")
        bc = code128.Code128(f"{order_number}-{i:02d}", barHeight=6 * mm, barWidth=0.2 * mm)
        bc.drawOn(c, (W - bc.width) / 2, 2 * mm)
        c.showPage()
    c.save()
    return buf.getvalue()

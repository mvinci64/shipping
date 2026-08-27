"""Piano di cartonizzazione del giorno — un PDF A4 con 4 ordini per pagina,
in griglia 2×2, con linee di taglio tratteggiate. Si stampa, si ritaglia in
4, e ogni pezzo si allega fisicamente all'ordine in laboratorio: è il
documento ufficiale pre-produzione (presunto — SKU non censiti segnalati),
distinto dalle etichette collo WP50/WP40 che arrivano dopo, a produzione
fatta (vedi app/labels.py, Fase 2).
"""
import io

from app.cartonize import cartonize_order

PAGE_W_MM = 210
PAGE_H_MM = 297
MARGIN_MM = 4
HEADER_H_MM = 7   # striscia riservata alla data pagina, fuori dai quadranti
FOOTER_H_MM = 8   # striscia riservata a "Totale" + disclaimer, dentro ogni quadrante


def _draw_quadrant(c, x0, y0, w, h, mm, ordine: dict):
    """Disegna il piano di un ordine dentro il rettangolo (x0,y0,w,h) — origine
    in basso a sinistra del quadrante. Interrompe il disegno (con '…') se il
    contenuto non entra, invece di scrivere fuori dal quadrante."""
    result = cartonize_order(ordine["righe"])
    y_top = y0 + h - MARGIN_MM * mm
    y_bottom = y0 + (MARGIN_MM + FOOTER_H_MM) * mm
    x = x0 + MARGIN_MM * mm
    x_right = x0 + w - MARGIN_MM * mm
    y = y_top

    def riga_disponibile(altezza_mm):
        return y - altezza_mm * mm >= y_bottom

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "VISCOTTA — piano cartonizzazione (presunto)")
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, ordine["order_number"])
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    c.drawString(x, y, ordine["cliente"][:44])
    y -= 6 * mm

    c.setFont("Helvetica-Bold", 8)
    n_tot = result["n_scatoloni"]
    for i, carton in enumerate(result["scatoloni"], 1):
        if not riga_disponibile(4):
            c.setFont("Helvetica-Oblique", 7)
            c.drawString(x, y, "… continua (vedi shipping-api per il dettaglio completo)")
            y -= 4 * mm
            break
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, y, f"Scatolone {i}/{n_tot} — {carton['peso_g'] / 1000:.2f} kg")
        y -= 4 * mm
        c.setFont("Helvetica", 7.5)
        for item in carton["contenuto"]:
            if not riga_disponibile(3.5):
                break
            c.drawString(x + 2 * mm, y, f"{item['sku']} ({item['formato']}) — {item['pezzi']} pz")
            y -= 3.5 * mm

    if result["non_censiti"]:
        y -= 1.5 * mm
        c.setFont("Helvetica-BoldOblique", 7.5)
        c.drawString(x, y, "SKU non censiti — da imballare a mano:")
        y -= 3.5 * mm
        c.setFont("Helvetica-Oblique", 7.5)
        for nc in result["non_censiti"]:
            if not riga_disponibile(3.5):
                break
            c.drawString(x + 2 * mm, y, f"{nc['qta']:g}× {nc['sku']}")
            y -= 3.5 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y0 + (MARGIN_MM + 4) * mm, f"Totale: {result['peso_totale_kg']:.2f} kg — {n_tot} scatoloni")
    c.setFont("Helvetica-Oblique", 6)
    c.drawString(x, y0 + MARGIN_MM * mm, "PRESUNTO — lotto/scadenza su etichette collo post-produzione")


def make_day_plan_pdf(data_consegna_iso: str, ordini: list[dict]) -> bytes:
    from reportlab.lib.units import mm as mm_unit
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W_MM * mm_unit, PAGE_H_MM * mm_unit))
    W, H = PAGE_W_MM * mm_unit, PAGE_H_MM * mm_unit
    header_h = HEADER_H_MM * mm_unit
    grid_h = H - header_h
    half_w, half_h = W / 2, grid_h / 2

    quadranti = [(0, half_h), (half_w, half_h), (0, 0), (half_w, 0)]  # alto-sx, alto-dx, basso-sx, basso-dx

    for pagina_idx in range(0, len(ordini), 4):
        gruppo = ordini[pagina_idx:pagina_idx + 4]

        c.setFont("Helvetica", 7)
        c.drawString(4 * mm_unit, H - 4 * mm_unit, f"Piano cartonizzazione {data_consegna_iso}")

        c.setDash(2, 2)
        c.line(half_w, 0, half_w, grid_h)
        c.line(0, half_h, W, half_h)
        c.setDash()

        for (qx, qy), ordine in zip(quadranti, gruppo):
            _draw_quadrant(c, qx, qy, half_w, half_h, mm_unit, ordine)

        c.showPage()

    c.save()
    return buf.getvalue()

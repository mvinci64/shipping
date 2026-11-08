"""Cartellone spedizioni in PDF — un foglio A4 per gruppo di uscita.

Stessa cosa che il reparto stampa oggi dal browser
(shipping-web/src/app/spedizioni/cartellone, modalità gruppi), ma generata
qui: serve un comando che produca il PDF senza passare dalla pagina, perché
i gruppi arrivano come nota da miniMRP e il giro "apri la pagina, incolla,
stampa" è l'unico pezzo manuale rimasto.

Scelte tenute identiche alla pagina web, per non avere due cartelloni
diversi in reparto:
- un invio = un cliente (più ordini dello stesso cliente nello stesso gruppo
  stanno su UNA riga: un collo, un ritiro — vedi CLAUDE.md);
- il titolo del foglio è il GIORNO DI PARTENZA, etichetta libera: i gruppi
  del piano di chiusura possono cadere anche di sabato/domenica;
- gli ordini non trovati a sistema, o fuori dal filtro "in prenotazione",
  vengono SEGNALATI sul foglio, non fatti sparire.
"""
import datetime
import io
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .labels import _a_capo, _tronca_a_larghezza

MARGINE = 14 * mm
# Oltre questo numero di invii il foglio si riempie: le righe successive
# vanno su una seconda pagina, con lo stesso titolo e "(segue)".
ALTEZZA_RIGA = 11 * mm


def raggruppa_per_cliente(righe: list[dict]) -> list[dict]:
    """Un invio per cliente, nell'ordine di prima comparsa (che è l'ordine
    deciso a monte, non alfabetico)."""
    per_cliente: dict[str, list[dict]] = {}
    for r in righe:
        per_cliente.setdefault(r["cliente"], []).append(r)
    return [{"cliente": cliente, "ordini": ordini} for cliente, ordini in per_cliente.items()]


def _data_breve(iso: str | None) -> str:
    if not iso:
        return "—"
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%d/%m")


def spezza_etichetta(etichetta: str) -> tuple[str, str]:
    """Etichetta del gruppo → (giorno, contesto). Le note di miniMRP
    intestano i gruppi come 'gio 19-11 — gruppo "prenotati metà novembre",
    chiude mercoledì 18': sul foglio in grande deve restare solo il giorno,
    il resto è contesto di produzione e va in piccolo nella testata."""
    giorno, contesto = (re.split(r"\s+(?:—|–|-{1,2})\s+", etichetta, maxsplit=1) + [""])[:2]
    return giorno.strip(), contesto.strip()


def _intestazione(c, larghezza, titolo: str, contesto: str, segue: bool) -> float:
    """Testata del foglio; torna la y da cui partire con le righe."""
    y = A4[1] - MARGINE
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGINE, y - 6 * mm, "SPEDIZIONI DEL GIORNO")
    c.setFont("Helvetica", 10)
    etichetta = f"{titolo} (segue)" if segue else titolo
    if contesto:
        etichetta = f"{etichetta} · {contesto}"
    # La testata parte dove finisce il titolo a sinistra: con le note
    # lunghe di miniMRP si sovrapponevano.
    x_min = MARGINE + c.stringWidth("SPEDIZIONI DEL GIORNO", "Helvetica-Bold", 18) + 6 * mm
    etichetta = _tronca_a_larghezza(c, etichetta, "Helvetica", 10, larghezza - MARGINE - x_min)
    c.drawRightString(larghezza - MARGINE, y - 6 * mm, etichetta)
    y -= 10 * mm
    c.setLineWidth(1.2)
    c.line(MARGINE, y, larghezza - MARGINE, y)
    return y - 12 * mm


def _riga_invio(c, larghezza, y: float, numero: int, invio: dict) -> float:
    """Una riga del cartellone: casella da spuntare, numero, cliente in
    grande, riferimenti ordine a destra. Torna la nuova y."""
    lato = 5 * mm
    c.setLineWidth(1)
    c.rect(MARGINE, y - lato + 1 * mm, lato, lato)

    c.setFont("Helvetica", 9)
    c.drawRightString(MARGINE + 13 * mm, y, str(numero))

    # Lo spazio del cliente finisce dove iniziano i riferimenti ordine.
    x_rif = larghezza - MARGINE - 52 * mm
    x_cliente = MARGINE + 16 * mm
    larghezza_cliente = x_rif - x_cliente - 4 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(MARGINE + 16 * mm, y, _tronca_a_larghezza(c, invio["cliente"], "Helvetica-Bold", 13, larghezza_cliente))
    if len(invio["ordini"]) > 1:
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x_cliente, y - 4 * mm, f"{len(invio['ordini'])} ORDINI IN UN SOLO INVIO")

    y_rif = y
    for o in invio["ordini"]:
        c.setFont("Helvetica", 7)
        c.drawRightString(larghezza - MARGINE, y_rif, f"{o['order_number']} · consegna {_data_breve(o.get('data_consegna'))}")
        y_rif -= 3.2 * mm
        if o.get("in_prenotazione") is False:
            c.setFont("Helvetica-Bold", 7)
            c.drawRightString(larghezza - MARGINE, y_rif, "DA VERIFICARE SUL PORTALE")
            y_rif -= 3.2 * mm

    # L'altezza della riga la decide il blocco più alto fra cliente e
    # riferimenti: con 3 ordini consolidati i riferimenti sforano.
    y_minima = min(y - ALTEZZA_RIGA, y_rif - 2 * mm)
    c.setLineWidth(0.4)
    c.line(MARGINE, y_minima + 4 * mm, larghezza - MARGINE, y_minima + 4 * mm)
    return y_minima


def _pie(c, larghezza):
    c.setLineWidth(1)
    c.line(MARGINE, MARGINE + 6 * mm, larghezza - MARGINE, MARGINE + 6 * mm)
    c.setFont("Helvetica", 7)
    c.drawString(MARGINE, MARGINE + 2 * mm, "reparto logistica · VISCOTTA")
    c.drawRightString(larghezza - MARGINE, MARGINE + 2 * mm, "gruppo di uscita deciso a monte, non dalle date del portale")


def _foglio(c, gruppo: dict):
    """Un gruppo: una o più pagine A4 (se le righe non ci stanno)."""
    larghezza = A4[0]
    invii = raggruppa_per_cliente(gruppo["righe"])
    titolo, contesto = spezza_etichetta(gruppo["etichetta"])
    y = _intestazione(c, larghezza, titolo, contesto, segue=False)

    c.setFont("Helvetica", 9)
    conteggio = f"{len(invii)} invii · {len(gruppo['righe'])} ordini" if len(invii) != len(gruppo["righe"]) else f"{len(invii)} {'invio' if len(invii) == 1 else 'invii'}"
    c.drawRightString(larghezza - MARGINE, y + 4 * mm, conteggio)
    c.setFont("Helvetica-Bold", 14)
    larghezza_titolo = larghezza - 2 * MARGINE - c.stringWidth(conteggio, "Helvetica", 9) - 6 * mm
    c.drawString(MARGINE, y + 3 * mm, _tronca_a_larghezza(c, titolo.upper(), "Helvetica-Bold", 14, larghezza_titolo))
    y -= 8 * mm

    if not invii:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(MARGINE, y, "— nessun ordine in questo gruppo —")
        y -= ALTEZZA_RIGA

    for i, invio in enumerate(invii, start=1):
        # Spazio minimo per una riga più il piede e l'eventuale blocco
        # "non trovati": sotto questa soglia si va a pagina nuova.
        if y < MARGINE + 40 * mm:
            _pie(c, larghezza)
            c.showPage()
            y = _intestazione(c, larghezza, titolo, contesto, segue=True)
        y = _riga_invio(c, larghezza, y, i, invio)

    if gruppo.get("mancanti"):
        y -= 6 * mm
        c.setLineWidth(1.5)
        altezza = 10 * mm
        c.rect(MARGINE, y - altezza + 4 * mm, larghezza - 2 * MARGINE, altezza)
        c.setFont("Helvetica-Bold", 8)
        testo = f"NON TROVATI A SISTEMA: {', '.join(gruppo['mancanti'])} — da verificare prima di spedire."
        for riga in _a_capo(c, testo, "Helvetica-Bold", 8, larghezza - 2 * MARGINE - 6 * mm, righe_max=2):
            c.drawString(MARGINE + 3 * mm, y, riga)
            y -= 4 * mm

    _pie(c, larghezza)
    c.showPage()


def make_cartellone_pdf(gruppi: list[dict]) -> bytes:
    """gruppi: [{"etichetta": "sab 07-11", "righe": [{order_number, cliente,
    data_consegna, in_prenotazione}, ...], "mancanti": ["ORD-..."]}, ...].
    Un foglio (almeno una pagina A4) per gruppo, nell'ordine dato."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Cartellone spedizioni — VISCOTTA")
    for gruppo in gruppi:
        _foglio(c, gruppo)
    c.save()
    return buf.getvalue()

from app.cartellone import make_cartellone_pdf, raggruppa_per_cliente

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from cartellone_pdf import parse_nota, parse_opzioni  # noqa: E402

# Nota reale di miniMRP (6 novembre 2026), incollata come arriva: tabella
# con cliente/città/quantità/date sulla stessa riga del numero d'ordine.
NOTA = """\
Gruppo 2 "SECONDO GRUPPO" — si chiude lunedì 9 novembre — 9 ordini — 1.423 pz
ORD-20260505-5931          TI.CO.VI. DI TIZIANA COSTA    Inveruno (MI)     424   pronto 2026-11-07   uscita 2026-11-08
IMPORT-DMLAB-20261020-01   ALIMENTARI AL ZIC SNC         Moltrasio (CO)     48   pronto 2026-11-07   uscita 2026-11-08

Gruppo 3 "TERZO GRUPPO" — tutti pronto 2026-11-11, uscita 2026-11-12
ORD-20260930-4454          DITTA LEONARDI SERGIO         Ravenna (RA)      402

Note da riportare, se le etichette hanno spazio:
- "pronto" = ultimo giorno di produzione; "uscita" = pronto + 1.
"""


def test_parse_nota_prende_gli_ordini_e_ignora_il_resto_della_riga():
    gruppi = parse_nota(NOTA)
    assert [g["ordini"] for g in gruppi] == [
        ["ORD-20260505-5931", "IMPORT-DMLAB-20261020-01"],
        ["ORD-20260930-4454"],
    ]
    assert gruppi[0]["etichetta"].startswith("Gruppo 2")


def test_parse_nota_scarta_le_note_di_coda_come_gruppi_vuoti():
    # Le righe senza numero d'ordine aprono un gruppo: quelle finali non ne
    # hanno nessuno e non devono diventare un foglio bianco.
    assert len(parse_nota(NOTA)) == 2


def test_parse_nota_non_confonde_le_date_con_numeri_dordine():
    assert parse_nota("solo testo 2026-11-08 e 07-11\n") == []


def test_parse_opzioni_etichetta_e_ordini():
    (gruppo,) = parse_opzioni(["lun 09-11=ORD-1234-5678, ORD-2222-3333"])
    assert gruppo == {"etichetta": "lun 09-11", "ordini": ["ORD-1234-5678", "ORD-2222-3333"]}


def test_raggruppa_per_cliente_tiene_lordine_di_comparsa():
    righe = [
        {"order_number": "A", "cliente": "BETA"},
        {"order_number": "B", "cliente": "ALFA"},
        {"order_number": "C", "cliente": "BETA"},
    ]
    invii = raggruppa_per_cliente(righe)
    assert [i["cliente"] for i in invii] == ["BETA", "ALFA"]
    assert len(invii[0]["ordini"]) == 2


def test_make_cartellone_pdf_produce_pdf_valido():
    gruppi = [{
        "etichetta": "lun 09-11",
        "righe": [
            {"order_number": "ORD-20260505-5931", "cliente": "TI.CO.VI. DI TIZIANA COSTA",
             "data_consegna": "2026-11-11", "in_prenotazione": True},
            {"order_number": "ORD-20261102-5007", "cliente": "TUTTO PER LA CASA SAS",
             "data_consegna": None, "in_prenotazione": False},
        ],
        "mancanti": ["ORD-INESISTENTE-0001"],
    }]
    assert make_cartellone_pdf(gruppi).startswith(b"%PDF-")


def test_make_cartellone_pdf_gruppo_vuoto_non_rompe():
    assert make_cartellone_pdf([{"etichetta": "x", "righe": [], "mancanti": []}]).startswith(b"%PDF-")


def test_spezza_etichetta_tiene_solo_il_giorno_in_grande():
    from app.cartellone import spezza_etichetta
    assert spezza_etichetta('gio 19-11 — gruppo "prenotati metà novembre", chiude mercoledì 18') == (
        "gio 19-11", 'gruppo "prenotati metà novembre", chiude mercoledì 18'
    )
    # Il trattino dentro la data non è un separatore: niente spazi intorno.
    assert spezza_etichetta("lun 16-11") == ("lun 16-11", "")

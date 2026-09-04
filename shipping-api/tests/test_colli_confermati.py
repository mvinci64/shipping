"""Test unitari sul parsing del codice scansionato — nessun accesso a DB
(per il flusso end-to-end vedi sql/colli_confermati.sql, da eseguire
manualmente prima di poter testare gli endpoint)."""
import pytest
from fastapi import HTTPException

from app.routers.cartonizzazioni import _parse_codice_collo


def test_parse_codice_collo_ordine_semplice():
    order_number, indice = _parse_codice_collo("ORD-0001-01")
    assert order_number == "ORD-0001"
    assert indice == 1


def test_parse_codice_collo_order_number_con_piu_trattini():
    # order_number reale ha la forma ORD-YYYYMMDD-NNNN: il codice del
    # barcode aggiunge un ulteriore "-NN" in coda, l'indice è sempre le
    # ultime 2 cifre
    order_number, indice = _parse_codice_collo("ORD-20260910-1234-02")
    assert order_number == "ORD-20260910-1234"
    assert indice == 2


def test_parse_codice_collo_spazi_bianchi_ignorati():
    order_number, indice = _parse_codice_collo("  ORD-0001-01  ")
    assert order_number == "ORD-0001"
    assert indice == 1


def test_parse_codice_collo_senza_indice_numerico_rifiutato():
    with pytest.raises(HTTPException) as exc:
        _parse_codice_collo("ORD-0001")
    assert exc.value.status_code == 422


def test_parse_codice_collo_indice_a_una_cifra_rifiutato():
    # il barcode stampa sempre l'indice su 2 cifre (i:02d) — un formato
    # diverso indica un codice non generato da noi
    with pytest.raises(HTTPException) as exc:
        _parse_codice_collo("ORD-0001-1")
    assert exc.value.status_code == 422


def test_parse_codice_collo_stringa_vuota_rifiutata():
    with pytest.raises(HTTPException) as exc:
        _parse_codice_collo("")
    assert exc.value.status_code == 422

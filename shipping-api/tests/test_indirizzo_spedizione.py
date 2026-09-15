from app.routers.spedizioni import _indirizzo_spedizione


def test_indirizzo_spedizione_formato_cap_in_coda():
    assert _indirizzo_spedizione("Via Patrioti Martiri 21, 18035") == "Via Patrioti Martiri 21"


def test_indirizzo_spedizione_toglie_nome_azienda_prima_della_via():
    # caso reale, IMPORT-DMLAB-20260629-01 (15/09/2026): 68 caratteri,
    # DHL rifiuta con 422 "expected maxLength: 45, actual: 68"
    indirizzo = "STELMOKA VIA VITTORIO EMANUELE II 11/13 20842 BESANA IN BRIANZA (MB)"
    risultato = _indirizzo_spedizione(indirizzo)
    assert risultato == "VIA VITTORIO EMANUELE II 11/13"
    assert len(risultato) <= 45


def test_indirizzo_spedizione_secondo_caso_reale():
    # IMPORT-DMLAB-20260716-01 (15/09/2026), stesso motivo
    indirizzo = "ENOTECA PIROVANO VIA DANTE ALIGHIERI 21 23884 CASTELLO DI BRIANZA (LC)"
    assert _indirizzo_spedizione(indirizzo) == "VIA DANTE ALIGHIERI 21"


def test_indirizzo_spedizione_senza_cap_tronca_comunque_a_45():
    indirizzo = "Nome Azienda Molto Lungo Via Something Extremely Long 12345678"
    risultato = _indirizzo_spedizione(indirizzo)
    assert len(risultato) <= 45


def test_indirizzo_spedizione_vuoto_non_solleva():
    assert _indirizzo_spedizione("") == ""
    assert _indirizzo_spedizione(None) == ""

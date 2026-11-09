import pytest

from app.cartonize import cartonize_order, collo_misto_box


def test_collo_misto_box_peso_somma_componenti_piu_tara():
    formato, sku, pezzi, peso, componenti, etichetta = collo_misto_box(
        "WP40", [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]
    )
    assert etichetta is None
    assert formato == "WP40"
    assert sku is None
    assert pezzi == 100
    # 50*(20+6) + 50*(20+6) + tara WP40 (150) = 1300 + 1300 + 150
    assert peso == 2750
    assert componenti == [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]


def test_cartonize_order_con_collo_misto_non_segnala_non_censiti():
    rows = [{"sku": "VP01", "qta": 50}, {"sku": "VP06", "qta": 50}]
    colli_misti = [{"formato": "WP40", "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]}]
    result = cartonize_order(rows, colli_misti=colli_misti)
    assert result["non_censiti"] == []
    assert result["n_scatoloni"] == 1
    entry = result["scatoloni"][0]["contenuto"][0]
    assert entry["sku"] is None
    assert entry["componenti"] == colli_misti[0]["componenti"]


def test_cartonize_order_collo_misto_lascia_il_resto_alla_cartonizzazione_normale():
    # 80 VP01 ordinati, solo 50 finiscono nel collo misto: i 30 residui
    # vanno in un WP40 proprio (VP01 ha PEZZI_PER_COLLO WP40=100 dal
    # 27/09/2026), niente più non_censiti
    rows = [{"sku": "VP01", "qta": 80}, {"sku": "VP06", "qta": 50}]
    colli_misti = [{"formato": "WP40", "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]}]
    result = cartonize_order(rows, colli_misti=colli_misti)
    assert result["non_censiti"] == []
    residuo = next(
        item for carton in result["scatoloni"] for item in carton["contenuto"]
        if item.get("sku") == "VP01"
    )
    assert residuo == {"formato": "WP40", "sku": "VP01", "pezzi": 30, "peso_g": 930}


def test_cartonize_order_collo_misto_quantita_eccessiva_solleva_errore():
    rows = [{"sku": "VP01", "qta": 10}, {"sku": "VP06", "qta": 50}]
    colli_misti = [{"formato": "WP40", "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]}]
    with pytest.raises(ValueError):
        cartonize_order(rows, colli_misti=colli_misti)


def test_cartonize_order_collo_misto_sku_non_censito_solleva_keyerror():
    rows = [{"sku": "SKU-IGNOTO", "qta": 50}]
    colli_misti = [{"formato": "WP40", "componenti": [{"sku": "SKU-IGNOTO", "pezzi": 50}]}]
    with pytest.raises(KeyError):
        cartonize_order(rows, colli_misti=colli_misti)


def test_cartonize_order_sfuso_non_entra_in_scatolone_gia_pieno_di_wp40():
    # ORD-20260505-4944 (17/09/2026): 6 WP40 (4 standard + 2 colli misti)
    # riempiono già lo scatolone (6/6 posti) — i prodotti sfusi (TCAP200SC,
    # TCAP500IR) non hanno più spazio fisico e devono finire in un secondo
    # scatolone, non essere infilati in quello pieno (bug: gli sfusi hanno
    # 0 posti, quindi entravano comunque finché non si aggiungeva il
    # controllo su posti_usati < POSTI_SCATOLONE).
    rows = [
        {"sku": "CANTS100", "qta": 12},
        {"sku": "CHMS50", "qta": 12},
        {"sku": "GRM100", "qta": 12},
        {"sku": "MSAL080", "qta": 12},
        {"sku": "TCAP200SC", "qta": 12},
        {"sku": "TCAP500IR", "qta": 6},
        {"sku": "VP01", "qta": 50},
        {"sku": "VP04", "qta": 50},
        {"sku": "VP05", "qta": 50},
        {"sku": "VP06", "qta": 50},
    ]
    colli_misti = [
        {"formato": "WP40", "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]},
        {"formato": "WP40", "componenti": [{"sku": "VP05", "pezzi": 50}, {"sku": "VP04", "pezzi": 50}]},
    ]
    result = cartonize_order(rows, colli_misti=colli_misti)
    assert result["n_scatoloni"] == 2
    primo, secondo = result["scatoloni"]
    assert primo["posti_usati"] == 6
    assert all(e["formato"] == "WP40" for e in primo["contenuto"])
    assert secondo["posti_usati"] == 0
    assert {e["sku"] for e in secondo["contenuto"]} == {"TCAP200SC", "TCAP500IR"}


def test_collo_misto_con_formato_e_scatolone_indice_fonde_due_scatoloni():
    """Caso reale ALIMENTAZIONE B.M. di Bergomas (ORD-20260628-7898,
    09/11/2026): la cartonizzazione automatica dà 3 scatoloni (6 posti,
    6 posti, 1 posto) e il reparto fonde il 2 e il 3. Forzando la scatola
    interna del terzo nel secondo si ottengono 2 scatoloni: il secondo va
    a 7 posti su 6 — l'operatore ha verificato fisicamente che ci sta —
    e la tara del WP40 resta nel peso."""
    rows = [
        {"sku": "TCAP075", "qta": 12}, {"sku": "CANTS100", "qta": 12},
        {"sku": "CHMS50", "qta": 12}, {"sku": "GRM100", "qta": 12},
        {"sku": "MSAL080", "qta": 12}, {"sku": "MCIOC080", "qta": 12},
        {"sku": "CMEN080", "qta": 12}, {"sku": "CIOCCM80SC", "qta": 12},
        {"sku": "VP01", "qta": 25}, {"sku": "VP04", "qta": 25},
        {"sku": "VP05", "qta": 25}, {"sku": "VP08", "qta": 25},
    ]
    assert cartonize_order(rows)["n_scatoloni"] == 3

    forzato = [{
        "formato": "WP40", "componenti": [{"sku": "VP08", "pezzi": 25}],
        "scatolone_indice": 2, "etichetta_sku": "VP08", "etichetta_pezzi": 25,
    }]
    result = cartonize_order(rows, colli_misti=forzato)
    assert result["n_scatoloni"] == 2
    assert result["posti_liberi_ultimo"] == 0  # 7 posti su 6, mai negativo
    secondo = result["scatoloni"][1]
    assert secondo["posti_usati"] == 7
    collo = secondo["contenuto"][-1]
    assert collo["formato"] == "WP40"
    assert collo["componenti"] == [{"sku": "VP08", "pezzi": 25}]
    assert collo["peso_g"] == 25 * (20 + 6) + 150  # grammatura + sovrappeso + tara WP40
    assert collo["etichetta"] == {"sku": "VP08", "pezzi": 25}


def test_kit_senza_distinta_segnalato_senza_cambiare_la_cartonizzazione():
    """SCATRM05A è censito in CONFEZIONI ma a miniMRP è un kit senza
    distinta base: la scatola si imballa, il contenuto non è stato
    prodotto. Il piano del giorno lo segnala (vedi day_plan)."""
    rows = [{"sku": "SCATRM05A", "qta": 6}, {"sku": "CHMS50", "qta": 12}]
    base = cartonize_order(rows)
    assert base["kit_senza_distinta"] == []

    result = cartonize_order(rows, kit_senza_distinta={"SCATRM05A", "NATA06"})
    assert result["kit_senza_distinta"] == [{"sku": "SCATRM05A", "qta": 6}]
    assert result["n_scatoloni"] == base["n_scatoloni"]
    assert result["peso_totale_kg"] == base["peso_totale_kg"]

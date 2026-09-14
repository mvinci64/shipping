import pytest

from app.cartonize import cartonize_order, collo_misto_box


def test_collo_misto_box_peso_somma_componenti_piu_tara():
    formato, sku, pezzi, peso, componenti = collo_misto_box(
        "WP40", [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]
    )
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
    # restano non censiti (VP01 non ha un PEZZI_PER_COLLO proprio)
    rows = [{"sku": "VP01", "qta": 80}, {"sku": "VP06", "qta": 50}]
    colli_misti = [{"formato": "WP40", "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]}]
    result = cartonize_order(rows, colli_misti=colli_misti)
    assert result["non_censiti"] == [{"sku": "VP01", "qta": 30}]


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

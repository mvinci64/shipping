"""Regressione (18/09/2026): _pesi_scatoloni_kg chiamava cartonize_order()
direttamente, ignorando i colli misti manuali dell'ordine — per
ORD-20260505-4944 (VP01/VP02/VP04/VP05/VP06, senza PEZZI_PER_COLLO
proprio) questo sottostimava peso e numero di scatoloni della spedizione
DHL reale (i pezzi finivano in non_censiti e sparivano dal calcolo).
_pesi_scatoloni_kg deve sempre passare da _cartonize_ordine_reale."""
from app.routers import cartonizzazioni, spedizioni


def test_pesi_scatoloni_kg_include_i_colli_misti_manuali(monkeypatch):
    colli_misti = [
        {"formato": "WP40", "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]},
    ]
    monkeypatch.setattr(cartonizzazioni.db, "fetch_colli_misti_per_cartonize", lambda order_number: colli_misti)

    ordine = {"righe": [{"sku": "VP01", "qta": 50}, {"sku": "VP06", "qta": 50}]}
    pesi = spedizioni._pesi_scatoloni_kg("ORD-TEST", ordine)

    # senza il fix: cartonize_order() diretta segnala VP01/VP06 come non
    # censiti e restituisce 0 scatoloni (422 "ordine senza prodotti censiti").
    # 2.75kg il collo misto (vedi test_collo_misto_box_peso_somma_componenti_
    # piu_tara) + 1.4kg tara scatolone/carta riempimento (TARA_SCATOLONE_G +
    # CARTA_RIEMPIMENTO_G).
    assert pesi == [4.15]

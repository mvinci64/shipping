"""_contrassegno_eur (18/09/2026): l'ordine non ha una colonna "modalità di
pagamento" dedicata — stessa logica della vista Ordini del Portal
(CASE WHEN payment_advance_discount THEN 'Anticipo' ELSE 'Contrassegno'
END, confermata dall'utente): pagato in anticipo -> niente contrassegno,
altrimenti -> contrassegno per l'intero grand_total. Il valore alimenta
dhl.crea_spedizione(contrassegno_eur=...), che aggiunge il servizio
contrassegno (KB): il corriere non deve rilasciare la merce senza prima
incassare."""
import pytest
from fastapi import HTTPException

from app.routers.spedizioni import _contrassegno_eur


def test_ordine_pagato_in_anticipo_non_ha_contrassegno():
    ordine = {"payment_advance_discount": True, "grand_total": 123.45}
    assert _contrassegno_eur("ORD-TEST", ordine) is None


def test_ordine_non_anticipato_richiede_contrassegno_per_intero_importo():
    ordine = {"payment_advance_discount": False, "grand_total": 260.04}
    assert _contrassegno_eur("ORD-TEST", ordine) == 260.04


def test_payment_advance_discount_null_si_comporta_come_contrassegno():
    # NULL su viscotta.orders.payment_advance_discount (mai valorizzato) ->
    # bool(None) è False in db.fetch_order, quindi contrassegno di default
    ordine = {"payment_advance_discount": False, "grand_total": 50.0}
    assert _contrassegno_eur("ORD-TEST", ordine) == 50.0


def test_contrassegno_senza_grand_total_solleva_422_esplicito():
    ordine = {"payment_advance_discount": False, "grand_total": None}
    with pytest.raises(HTTPException) as exc:
        _contrassegno_eur("ORD-TEST", ordine)
    assert exc.value.status_code == 422

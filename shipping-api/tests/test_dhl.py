"""Test unitari sul client DHL e sul parsing indirizzo — nessuna chiamata
reale a MyDHL API (nessuna credenziale/rete richiesta)."""
import pytest
from fastapi import HTTPException

from app import dhl
from app.routers.spedizioni import _estrai_cap, _iso2


def test_estrai_cap_da_indirizzo():
    assert _estrai_cap("Via Patrioti Martiri 21, 18035") == "18035"


def test_estrai_cap_mancante_solleva_422():
    with pytest.raises(HTTPException) as exc_info:
        _estrai_cap("Via senza CAP")
    assert exc_info.value.status_code == 422


def test_iso2_italia():
    assert _iso2("Italia") == "IT"


def test_iso2_sconosciuto_solleva_422():
    with pytest.raises(HTTPException) as exc_info:
        _iso2("Ruritania")
    assert exc_info.value.status_code == 422


def test_valida_spedizione_senza_credenziali_solleva_config_error(monkeypatch):
    monkeypatch.delenv("DHL_ACCOUNT_NUMBER", raising=False)
    monkeypatch.delenv("DHL_API_USERNAME", raising=False)
    monkeypatch.delenv("DHL_API_PASSWORD", raising=False)
    with pytest.raises(dhl.DHLConfigError):
        dhl.valida_spedizione(
            destinatario_cap="18035",
            destinatario_citta="Dolceacqua",
            destinatario_provincia="IM",
            destinatario_paese="IT",
            pesi_scatoloni_kg=[3.2],
            data_spedizione_iso="2026-08-31",
        )


def test_package_solo_peso_senza_dimensioni_censite(monkeypatch):
    monkeypatch.delenv("DHL_SCATOLONE_LUNGHEZZA_CM", raising=False)
    monkeypatch.setattr(dhl, "SCATOLONE_DIM_CM", {"lunghezza": None, "larghezza": None, "altezza": None})
    package = dhl._package(3.2)
    assert package == {"weight": 3.2}


def _kwargs_crea_spedizione(**override):
    kwargs = dict(
        order_number="TEST-001",
        product_code="N",
        destinatario_nome="Cliente Prova",
        destinatario_email="prova@example.com",
        destinatario_telefono="0000000000",
        destinatario_indirizzo="Via Prova 1",
        destinatario_cap="18035",
        destinatario_citta="Dolceacqua",
        destinatario_provincia="IM",
        destinatario_paese="IT",
        pesi_scatoloni_kg=[3.2],
        data_spedizione_iso="2026-09-02",
    )
    kwargs.update(override)
    return kwargs


def test_crea_spedizione_senza_credenziali_solleva_config_error(monkeypatch):
    monkeypatch.delenv("DHL_ACCOUNT_NUMBER", raising=False)
    monkeypatch.delenv("DHL_API_USERNAME", raising=False)
    monkeypatch.delenv("DHL_API_PASSWORD", raising=False)
    with pytest.raises(dhl.DHLConfigError):
        dhl.crea_spedizione(**_kwargs_crea_spedizione())


def test_crea_spedizione_senza_contatto_mittente_solleva_config_error(monkeypatch):
    monkeypatch.setenv("DHL_ACCOUNT_NUMBER", "127990547")
    monkeypatch.setenv("DHL_API_USERNAME", "user")
    monkeypatch.setenv("DHL_API_PASSWORD", "pass")
    monkeypatch.setattr(dhl, "ORIGIN_COMPANY_NAME", "")
    with pytest.raises(dhl.DHLConfigError):
        dhl.crea_spedizione(**_kwargs_crea_spedizione())


def _kwargs_richiedi_pickup(**override):
    kwargs = dict(
        shipment_tracking_number="7228978945",
        product_code="N",
        pesi_scatoloni_kg=[3.2],
        data_pickup_iso="2026-09-02",
    )
    kwargs.update(override)
    return kwargs


def test_richiedi_pickup_senza_credenziali_solleva_config_error(monkeypatch):
    monkeypatch.delenv("DHL_ACCOUNT_NUMBER", raising=False)
    monkeypatch.delenv("DHL_API_USERNAME", raising=False)
    monkeypatch.delenv("DHL_API_PASSWORD", raising=False)
    with pytest.raises(dhl.DHLConfigError):
        dhl.richiedi_pickup(**_kwargs_richiedi_pickup())


def test_richiedi_pickup_senza_contatto_mittente_solleva_config_error(monkeypatch):
    monkeypatch.setenv("DHL_ACCOUNT_NUMBER", "127990547")
    monkeypatch.setenv("DHL_API_USERNAME", "user")
    monkeypatch.setenv("DHL_API_PASSWORD", "pass")
    monkeypatch.setattr(dhl, "ORIGIN_COMPANY_NAME", "")
    with pytest.raises(dhl.DHLConfigError):
        dhl.richiedi_pickup(**_kwargs_richiedi_pickup())

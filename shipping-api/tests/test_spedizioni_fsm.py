"""Test unitari sulla logica di selezione prodotto DHL — nessuna chiamata
reale, nessun accesso a DB (per la FSM completa vedi sql/spedizioni_fsm.sql,
da eseguire manualmente prima di poter testare gli endpoint end-to-end)."""
from app.routers.spedizioni import _scegli_prodotto


def _risposta_con_prodotti(*nomi_prezzi):
    return {
        "products": [
            {
                "productName": nome,
                "productCode": nome[:1],
                "totalPrice": [{"currencyType": "BILLC", "priceCurrency": "EUR", "price": prezzo}],
            }
            for nome, prezzo in nomi_prezzi
        ]
    }


def test_sceglie_express_domestic_anche_se_non_primo():
    risposta = _risposta_con_prodotti(
        ("MEDICAL EXPRESS", 133.89),
        ("EXPRESS DOMESTIC 12:00", 43.91),
        ("EXPRESS DOMESTIC", 25.87),
        ("EXPRESS EASY", 49.01),
    )
    product_code, prezzo = _scegli_prodotto(risposta)
    assert product_code == "E"
    assert prezzo == 25.87


def test_fallback_al_primo_prodotto_se_niente_express_domestic():
    risposta = _risposta_con_prodotti(("MEDICAL EXPRESS", 133.89))
    product_code, prezzo = _scegli_prodotto(risposta)
    assert product_code == "M"
    assert prezzo == 133.89

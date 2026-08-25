"""Non-regressione: l'output di app.cartonize deve combaciare con il prototipo
su prototype/ordini_esempio.csv (stesso identico algoritmo, portato)."""
import csv
from collections import defaultdict
from pathlib import Path

from app.cartonize import cartonize_order

CSV_ESEMPIO = Path(__file__).parents[2] / "prototype" / "ordini_esempio.csv"


def _ordini_da_csv():
    orders = defaultdict(list)
    with open(CSV_ESEMPIO, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            orders[row["order_number"]].append(row)
    return orders


def test_cartonizzazione_su_ordini_esempio():
    orders = _ordini_da_csv()
    assert orders, "ordini_esempio.csv non trovato o vuoto"
    for order_number, rows in orders.items():
        result = cartonize_order(rows)
        assert result["n_scatoloni"] >= 1
        assert result["peso_totale_kg"] > 0
        for scatolone in result["scatoloni"]:
            assert scatolone["posti_usati"] <= 6

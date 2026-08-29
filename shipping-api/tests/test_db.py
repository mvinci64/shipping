"""Test contro il DB reale (stesso schema condiviso Portal/miniMRP/EasyFatt).
Richiede DATABASE_URL in .env — skippati altrimenti."""
import os

import pytest

from app import db

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL non impostata")


def test_fetch_ultimo_lotto_sku_esistente():
    lotto = db.fetch_ultimo_lotto("CHMS50")
    assert lotto is not None
    assert lotto["lotto"]
    assert lotto["scadenza"]


def test_fetch_ultimo_lotto_sku_inesistente():
    assert db.fetch_ultimo_lotto("SKU-INESISTENTE-XYZ") is None

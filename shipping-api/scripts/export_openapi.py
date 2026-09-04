"""Esporta lo schema OpenAPI di shipping-api come JSON statico, da cui
client-ts genera i tipi TS (vedi client-ts/README.md). Non richiede DB né
credenziali DHL: FastAPI costruisce lo schema dalle sole firme dei router,
non esegue gli endpoint.

Uso:
    cd shipping-api && python scripts/export_openapi.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

OUT_PATH = Path(__file__).resolve().parent.parent.parent / "client-ts" / "openapi.json"

if __name__ == "__main__":
    schema = app.openapi()
    OUT_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Scritto {OUT_PATH} ({len(schema['paths'])} path)")

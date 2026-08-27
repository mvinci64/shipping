# shipping-api

Servizio FastAPI del dominio spedizioni VISCOTTA (Fase 1 → Fase 2). Contiguo al miniMRP (Python); vedi `../valutazione-cartonizzazione.md` e `../piano-sprint.md` per il contesto architetturale.

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # imposta DATABASE_URL

uvicorn app.main:app --reload
```

- `GET /health` — stato servizio + connessione DB
- `POST /cartonizzazioni` — cartonizzazione da righe sku/qta passate nel body (per test/integrazioni esterne)
- `POST /cartonizzazioni/etichette-colli` — come sopra, ma PDF con un'etichetta per ogni collo interno WP50/WP40 (lotto/quantità, placeholder finché non c'è l'integrazione con `viscotta.ordini_produzione` in Fase 2)
- `GET /cartonizzazioni/{order_number}` — cartonizzazione di un ordine reale, letto da `viscotta.orders`/`order_items` (richiede `DATABASE_URL`)
- `GET /cartonizzazioni/{order_number}/etichette-colli` — PDF etichette colli per un ordine reale
- `GET /cartonizzazioni/piano-giorno/{data_consegna}` — piano cartonizzazione del giorno: un PDF A4 con 4 ordini per pagina (2×2, linee di taglio), da stampare e allegare fisicamente a ogni ordine in laboratorio (documento ufficiale pre-produzione, distinto dalle etichette collo che arrivano a produzione fatta)

## Test

```bash
pip install pytest
pytest
```

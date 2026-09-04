# shipping-api

Servizio FastAPI del dominio spedizioni VISCOTTA (Fase 1 → Fase 2). Contiguo al miniMRP (Python); vedi `../valutazione-cartonizzazione.md` e `../piano-sprint.md` per il contesto architetturale.

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # imposta DATABASE_URL, credenziali MyDHL, indirizzo origine

# Prima di usare gli endpoint /spedizioni (FSM), eseguire la DDL una tantum
# sul DB reale (crea la tabella viscotta.spedizioni — DDL manuale, non
# automatica: modifica strutturale su un DB condiviso col Portal/BI/miniMRP)
psql "$DATABASE_URL" -f ../sql/spedizioni_fsm.sql

uvicorn app.main:app --reload
```

- `GET /health` — stato servizio + connessione DB
- `POST /cartonizzazioni` — cartonizzazione da righe sku/qta passate nel body (per test/integrazioni esterne)
- `POST /cartonizzazioni/etichette-colli` — come sopra, ma PDF con un'etichetta per ogni collo interno WP50/WP40 (lotto/quantità, placeholder finché non c'è l'integrazione con `viscotta.ordini_produzione` in Fase 2)
- `GET /cartonizzazioni/{order_number}` — cartonizzazione di un ordine reale, letto da `viscotta.orders`/`order_items` (richiede `DATABASE_URL`)
- `GET /cartonizzazioni/{order_number}/etichette-colli` — PDF etichette colli per un ordine reale, con lotto/scadenza reali da `easyfatt.tmovmagazz` (ultimo carico per SKU — niente più placeholder, salvo SKU mai caricati in EasyFatt)
- `GET /cartonizzazioni/{order_number}/etichette-scatolone` — PDF riepilogo scatolone (una pagina per collo di spedizione), stesso formato/stampante 15×10 cm delle etichette colli — non sostituisce l'etichetta ufficiale del corriere
- `GET /cartonizzazioni/piano-giorno/{data_consegna}` — piano cartonizzazione del giorno: un PDF A4 con 4 ordini per pagina (2×2, linee di taglio), da stampare e allegare fisicamente a ogni ordine in laboratorio (documento ufficiale pre-produzione, distinto dalle etichette collo che arrivano a produzione fatta)
- `POST /spedizioni/valida/{order_number}` — quota la spedizione via MyDHL API (POST `/rates`) per un ordine reale, senza salvare nulla: è la versione "usa e getta" della quotazione, per controlli rapidi

### Conferma collo a fine linea

Il reparto conferma da `shipping-web` (`/spedizioni/{order_number}`), o digitando a mano il codice `<order_number>-NN` letto sull'etichetta scatolone (nessun barcode: tolto il 04/09/2026, confondeva in reparto — la conferma non è pensata per la scansione):

- `POST /cartonizzazioni/colli/conferma` — body `{"codice": "<order_number>-NN"}`, idempotente (confermare due volte non è un errore)
- `GET /cartonizzazioni/{order_number}/colli` — stato: `n_totale`/`confermati`/`mancanti`/`completo`
- `DELETE /cartonizzazioni/{order_number}/colli/{indice_collo}` — annulla una conferma (errore)

`POST /spedizioni/{id}/conferma` rifiuta con **409** se `completo` non è `true` per l'ordine: non si può confermare una spedizione reale (costo e ritiro reali) con colli non ancora confermati.

Richiede la tabella `viscotta.colli_confermati` — vedi `psql -f ../sql/colli_confermati.sql`.

### FSM spedizioni: `bozza → confermata → ritirata`

Ogni transizione che ha effetto reale su DHL (crea spedizione, prenota ritiro) richiede una chiamata esplicita — mai automatica — così l'operatore controlla sempre la bozza prima di procedere:

- `POST /spedizioni?order_number=...` — crea la bozza: quota via `/rates` (nessun effetto reale) e salva in `viscotta.spedizioni` (stato `bozza`)
- `GET /spedizioni/{id}` — dettaglio di una spedizione, in qualunque stato
- `POST /spedizioni/{id}/conferma` — **effetto reale**: `bozza → confermata`, crea la spedizione DHL vera con etichetta (`dhl.crea_spedizione`). Se DHL rifiuta, stato → `fallita` (bozza resta consultabile, nessun retry automatico)
- `GET /spedizioni/{id}/etichetta` — PDF etichetta ufficiale DHL, disponibile dopo la conferma
- `POST /spedizioni/{id}/pickup` — **effetto reale**: `confermata → ritirata`, prenota il ritiro vero (`dhl.richiedi_pickup`)
- `DELETE /spedizioni/{id}` — cancella la bozza (solo se ancora in stato `bozza`: nessun effetto DHL da annullare)

Richiede la tabella `viscotta.spedizioni` — vedi `psql -f sql/spedizioni_fsm.sql` sopra.

## Test

```bash
pip install pytest
pytest
```

## Contratto OpenAPI e client TS

Lo schema OpenAPI è generato dalle route FastAPI (nessuna chiamata DB/DHL). Il client TS tipizzato consumato da `shipping-web` (e potenzialmente dal Portal) vive in `../client-ts` — vedi `../client-ts/README.md`.

```bash
python scripts/export_openapi.py   # scrive ../client-ts/openapi.json
```

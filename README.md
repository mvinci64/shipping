# Shipping

Sistema di cartonizzazione e spedizione VISCOTTA: dalle prenotazioni dell'Order Portal agli scatoloni ottimizzati, etichettati e spediti.

## Contenuto del repository

| Percorso | Cosa contiene |
|---|---|
| `valutazione-cartonizzazione.md` | Valutazione architetturale: le 4 opzioni, il percorso a fasi, modello dati e viste BI |
| `docs/` | Versioni Word: documento tecnico e versione divulgativa per il team di produzione |
| `sql/anagrafica_configurazioni.sql` | DDL PostgreSQL dell'anagrafica configurazioni (Fase 1) + viste V1–V7 |
| `sql/fase1_seed_censimento.sql` | Estensione DDL (modello a posti) + seed dal censimento imballi del 26/08 |
| `sql/bi/` | Kit Fase 0 per Metabase: query read-only Q1–Q6 (simulazione e cartonizzazione attesa) |
| `prototype/` | Prototipo eseguibile: cartonizzazione → pesi → etichette PDF → bozza DHL |

## Percorso a fasi

**Fase 0** (fatta): simulazione read-only in Metabase sugli ordini storici. **Fase 1** (in corso): anagrafica configurazioni nel DB del Portal, prototipo etichette + bozza DHL. **Fase 2**: modulo operativo a valle del miniMRP con lotto/scadenza in etichetta. **Fase 3** (futuro): app logistica dedicata — `shipping-api` (Python/FastAPI) + `shipping-web` (TS/React).

## Prototipo — quick start

```bash
cd prototype
pip install -r requirements.txt
python cartonize.py ordini_esempio.csv -o out/
```

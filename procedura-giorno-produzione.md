# Procedura sequenziale del giorno di produzione

Documento tecnico che rende esplicito il coordinamento oggi implicito tra produzione, packaging e spedizione (le stesse 3 persone — vedi `CLAUDE.md`). Copre la sequenza reale dei sistemi coinvolti, da quando un lotto esce dal laboratorio a quando la spedizione DHL è confermata.

## Il vincolo che guida tutta la sequenza

**L'ETL EasyFatt → BI (`bi.viscotta.com`) è lanciato a mano, senza orario fisso.** `easyfatt.tmovmagazz` — la tabella da cui `shipping-api` legge il lotto reale (`db.fetch_ultimo_lotto`, vedi `shipping-api/app/db.py:91`) — è la **stessa tabella** scritta da quell'ETL sull'RDS condiviso. Non è una replica separata più vicina al tempo reale.

Conseguenza diretta: **nessuna etichetta con lotto reale può essere generata prima che l'ETL sia stato rilanciato dopo il carico del giorno.** Se l'etichetta viene richiesta prima, o `fetch_ultimo_lotto` non trova nulla (SKU mai caricato secondo l'RDS) o — peggio — trova l'ultimo carico *precedente*, di un giorno diverso, e lo stampa come se fosse quello giusto senza segnalare errore.

Questo sposta il problema identificato in `piano-sprint.md` (Sprint 3, "caso limite `fetch_ultimo_lotto`") da un dettaglio implementativo a un vincolo di processo: **il timing dell'ETL è il vero trigger**, non il carico in laboratorio in sé.

## Sequenza del giorno

| # | Passo | Sistema | Chi | Effetto reale? |
|---|---|---|---|---|
| 1 | Produzione fisica del lotto in laboratorio | — | Team produzione | No |
| 2 | Registrazione carico di magazzino (lotto, scadenza, quantità) | EasyFatt | Chi opera EasyFatt | Sì (nel gestionale) |
| 3 | **Lancio manuale dell'ETL EasyFatt → BI** | BI (`bi.viscotta.com`) | Da definire — oggi non ha owner esplicito | Sì — è il gate che sblocca tutto il resto |
| 4 | `easyfatt.tmovmagazz` sull'RDS condiviso riflette il carico | RDS condiviso | — (automatico, conseguenza del 3) | — |
| 5 | Cartonizzazione: `POST /cartonizzazioni` calcola scatoloni/pesi | shipping-api | Reparto packaging | No |
| 6 | Etichette collo interno con lotto/scadenza reali: `GET /cartonizzazioni/{order_number}/etichette-colli` | shipping-api → `easyfatt.tmovmagazz` | Reparto packaging | No, ma **richiede che il passo 3 sia già avvenuto per quell'ordine** |
| 7 | Bozza spedizione: `POST /spedizioni` (quotazione DHL, nessun effetto reale) | shipping-api → DHL `/rates` | Reparto spedizione | No |
| 8 | Conferma spedizione: `POST /spedizioni/{id}/conferma` | shipping-api → DHL `/shipments` | Reparto spedizione | **Sì — irreversibile, costo reale** |
| 9 | Richiesta ritiro: `POST /spedizioni/{id}/pickup` | shipping-api → DHL `/pickups` | Reparto spedizione | **Sì — irreversibile, ritiro reale** |

Il passo 8 fallisce (stato `fallita`, non un bug) se il cliente non ha telefono in nessuna fonte — vedi `piano-sprint.md`, mitigato parzialmente con fallback su `easyfatt.tanagrafica`.

## Il punto critico da decidere

Il passo 3 è oggi l'unico anello della catena senza owner esplicito e senza orario. Finché resta così, i passi 5-6 (cartonizzazione ed etichette) possono essere eseguiti "troppo presto" rispetto al passo 3, con il rischio di lotto sbagliato o mancante descritto sopra.

Opzioni, dalla più semplice alla più strutturale:

1. **Owner e orario fissi per il passo 3** — decisione organizzativa, non tecnica: chi lancia l'ETL e a che ora (es. fine turno produzione, prima che si stampino le etichette). Costo zero di sviluppo, ma dipende dalla disciplina operativa.
2. **Schedulare l'ETL** (es. ogni 15–30 minuti) invece di lanciarlo a mano — sposta il problema da "chi se ne ricorda" a "quanto ritardo massimo accettiamo". Da valutare con chi segue il progetto BI (fuori dal perimetro di questo repo).
3. **Bloccare lato shipping-api** — far fallire esplicitamente (invece di stampare un lotto vecchio in silenzio) `GET /cartonizzazioni/{order_number}/etichette-colli` se l'ultimo carico trovato per lo SKU non è del giorno atteso. Non risolve il ritardo, ma trasforma un errore silenzioso in un errore visibile — utile come rete di sicurezza indipendentemente dalle opzioni 1/2.

Raccomandazione: opzione 1 subito (costo zero, chiude il buco operativo oggi), opzione 3 come rete di sicurezza tecnica in Sprint 3, opzione 2 da discutere con BI se il volume di ordini/giorno rende insostenibile il lancio manuale.

## Aperto

- Chi è owner del lancio ETL non è definito — da assegnare.
- Non è documentato se l'ETL è idempotente (rilanciarlo più volte lo stesso giorno crea duplicati in `tmovmagazz`?) — da verificare con chi segue il progetto BI prima di proporre lo schedule (opzione 2).

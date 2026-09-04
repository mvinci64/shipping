# Procedura sequenziale del giorno di produzione

Documento tecnico che rende esplicito il coordinamento oggi implicito tra produzione, packaging e spedizione (le stesse 3 persone — vedi `CLAUDE.md`). Copre la sequenza reale dei sistemi coinvolti, da quando un lotto esce dal laboratorio a quando la spedizione DHL è confermata.

## Il vincolo che guida tutta la sequenza

**L'ETL EasyFatt → BI (`bi.viscotta.com`) è lanciato a mano, senza orario fisso.** `easyfatt.tmovmagazz` — la tabella da cui `shipping-api` legge il lotto reale (`db.fetch_ultimo_lotto`, vedi `shipping-api/app/db.py:91`) — è la **stessa tabella** scritta da quell'ETL sull'RDS condiviso. Non è una replica separata più vicina al tempo reale.

Conseguenza diretta: **nessuna etichetta con lotto reale può essere generata prima che l'ETL sia stato rilanciato dopo il carico del giorno.** Se l'etichetta viene richiesta prima, o `fetch_ultimo_lotto` non trova nulla (SKU mai caricato secondo l'RDS) o — peggio — trova l'ultimo carico *precedente*, di un giorno diverso, e lo stampa come se fosse quello giusto senza segnalare errore.

**Il lotto è unico per data+prodotto** (confermato 31/08/2026): tutti gli ordini che spediscono lo stesso prodotto nello stesso giorno condividono legittimamente lo stesso lotto — non è un errore, è il comportamento corretto. Questo significa che **non serve un trigger continuo o in tempo reale**: basta che l'ETL giri **una volta a fine giornata**, dopo l'ultimo carico registrato in EasyFatt e prima di stampare le etichette di quel giorno. L'unica urgenza reale è sull'ultimo prodotto inserito nell'ultimo scatolone di giornata — tutto il resto può aspettare tranquillamente la chiusura del turno.

## Sequenza del giorno

| # | Passo | Sistema | Chi | Effetto reale? |
|---|---|---|---|---|
| 1 | Produzione fisica del lotto in laboratorio | — | Team produzione | No |
| 2 | Registrazione carico di magazzino (lotto, scadenza, quantità) | EasyFatt | Chi opera EasyFatt | Sì (nel gestionale) |
| 3 | **Lancio manuale dell'ETL EasyFatt → BI, a fine giornata di produzione** | BI (`bi.viscotta.com`) | Da definire — oggi non ha owner esplicito | Sì — è il gate che sblocca tutto il resto |
| 4 | `easyfatt.tmovmagazz` sull'RDS condiviso riflette il carico | RDS condiviso | — (automatico, conseguenza del 3) | — |
| 5 | Cartonizzazione: `POST /cartonizzazioni` calcola scatoloni/pesi | shipping-api | Reparto packaging | No |
| 6 | Etichette collo interno con lotto/scadenza reali: `GET /cartonizzazioni/{order_number}/etichette-colli` | shipping-api → `easyfatt.tmovmagazz` | Reparto packaging | No, ma **richiede che il passo 3 sia già avvenuto quel giorno** |
| 7 | Etichetta scatolone (riepilogo interno, una per collo): `GET /cartonizzazioni/{order_number}/etichette-scatolone` | shipping-api | Reparto packaging | No |
| 8 | Chiusura fisica di ogni scatolone e scansione del suo barcode a fine linea: `POST /cartonizzazioni/colli/conferma` (body `{"codice": "<ordine>-NN"}`, il testo stampato sul barcode del passo 7 — nessuna digitazione manuale) | shipping-api → `viscotta.colli_confermati` | Reparto packaging | No, ma **è il gate del passo 10**: se un collo non viene scansionato, la conferma spedizione lo rifiuta |
| 9 | Bozza spedizione: `POST /spedizioni` (quotazione DHL, nessun effetto reale) | shipping-api → DHL `/rates` | Reparto spedizione | No |
| 10 | Conferma spedizione: `POST /spedizioni/{id}/conferma` | shipping-api → DHL `/shipments` | Reparto spedizione | **Sì — irreversibile, costo reale** |
| 11 | Richiesta ritiro: `POST /spedizioni/{id}/pickup` | shipping-api → DHL `/pickups` | Reparto spedizione | **Sì — irreversibile, ritiro reale** |

Il passo 10 rifiuta con 409 se il passo 8 non è stato completato per tutti gli scatoloni dell'ordine (vedi `GET /cartonizzazioni/{order_number}/colli` per lo stato: confermati/mancanti) — aggiunto il 04/09/2026 perché senza questo controllo si poteva confermare una spedizione reale (costo reale, ritiro reale) anche con uno scatolone ancora aperto sul tavolo. Il passo 10 fallisce anche (stato `fallita`, non un bug) se il cliente non ha telefono in nessuna fonte — vedi `piano-sprint.md`, mitigato parzialmente con fallback su `easyfatt.tanagrafica`.

Il codice scansionato al passo 8 non contiene lotto/scadenza: conferma solo che quello scatolone è stato fisicamente chiuso. Il passo 8 non ha una dipendenza dal passo 3 (l'ETL) — a differenza del passo 6, può avvenire in qualunque momento dopo la cartonizzazione.

## Il punto critico da decidere

Il passo 3 è oggi l'unico anello della catena senza owner esplicito e senza orario. Finché resta così, i passi 5-6 (cartonizzazione ed etichette) possono essere eseguiti "troppo presto" rispetto al passo 3 di quel giorno, con il rischio di lotto mancante o di un giorno precedente in etichetta.

Raccomandazione (unica opzione necessaria, dato che il lotto è unico per data+prodotto e non serve tempo reale): **owner e orario fissi per il passo 3** — decisione organizzativa, non tecnica: chi lancia l'ETL e a che ora, a fine turno di produzione, prima che si stampino le etichette del giorno. Costo zero di sviluppo.

Resta comunque utile, come rete di sicurezza tecnica a basso costo (non urgente): far fallire esplicitamente `GET /cartonizzazioni/{order_number}/etichette-colli` se l'ultimo carico trovato per lo SKU non è del giorno atteso, invece di stampare in silenzio il lotto di un giorno precedente — copre il caso in cui il passo 3 salti per errore un giorno.

## Aperto

- Chi è owner del lancio ETL non è definito — da assegnare.

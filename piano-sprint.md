# Shipping — Piano sprint

Piano di sviluppo a sprint per portare il dominio spedizioni da prototipo (`prototype/cartonize.py`) a servizio in produzione, secondo il percorso a fasi definito in `valutazione-cartonizzazione.md` (Fase 0 fatta, Fase 1 in corso, Fase 2/3 da avviare).

Contesto: il sistema informativo VISCOTTA comprende quattro progetti, ciascuno con Claude Code — Order Portal (TS, IDEA), miniMRP (Python, PyCharm), BI (Python, PyCharm), Shipping (questo repo). Shipping dipende dal Portal per anagrafica clienti/ordini e dal miniMRP per lotto/scadenza a fine linea; non li modifica.

Durata sprint indicativa: 2 settimane. Le stime vanno adattate al fatto che oggi produzione+packaging+spedizione sono le stesse 3 persone.

---

## Stato al 04/09/2026

| Sprint | Stato |
|---|---|
| Sprint 1 — Scaffolding FastAPI | ✅ Chiuso |
| Sprint 2 — FSM spedizione + DHL | ✅ Sostanzialmente chiuso (DHL in produzione dal 31/08/2026) — **debito tecnico aperto**: adapter BRT e interfaccia comune corriere, mai iniziati |
| Sprint 3 — Etichette lotto reale + endpoint operativo | ✅ Chiuso |
| Sprint 4 — `shipping-web` MVP | 🔶 In corso — scaffold e vista ordini da spedire (sola lettura) fatti; azione conferma+stampa dalla UI e auth/permessi ancora da fare |
| Sprint 5 — Hardening e rollout | ⬜ Non iniziato |

**Urgenza operativa**: 5 spedizioni reali previste nei prossimi giorni, operatività a partire dalla settimana dell'11/09/2026. Il flusso end-to-end (cartonizzazione → etichette colli con lotto reale → etichetta scatolone → scansione fine linea → bozza → conferma con gate sui colli → pickup) è **completo e testato**, utilizzabile oggi tramite `shipping-api` in locale (parla già con DB reale e MyDHL in produzione) anche senza `shipping-web` — vedi `procedura-giorno-produzione.md`. `shipping-web` è per ora solo di consultazione (`/spedizioni`, sola lettura): le azioni restano sulle chiamate dirette a `shipping-api`.

---

## Sprint 1 — Consolidare Fase 1 e scaffolding FastAPI

Obiettivo: chiudere i punti aperti dell'anagrafica configurazioni e avere `shipping-api` come progetto FastAPI reale, con la logica di `cartonize.py` esposta come endpoint.

- Finalizzare `sql/anagrafica_configurazioni.sql` / `sql/fase1_seed_censimento.sql`: SKU scatole regalo/Natale, tara scatolone pesata (oggi stimata 400 g), pesature dei colli marcati `derivato` (vista `vw_peso_confezione`)
- Confermare con il team lo stato ordine da cartonizzare (oggi filtro `status = 'submitted'` in Q6 — verificare che corrisponda a "in prenotazione")
- Scaffold `shipping-api/` (FastAPI, struttura cartelle, `pyproject.toml`/venv, connessione PostgreSQL schema `viscotta`, `GET /health`)
- Portare la logica di cartonizzazione di `cartonize.py` in `POST /cartonizzazioni` (input: ordine o lista ordini; output: scatoloni + pesi, stesso formato di `out/cartonizzazione.json`)
- Portare la generazione etichette **per collo interno** (WP50/WP40, lotto+quantità — `make_inner_labels` nel prototipo) come endpoint separato: è l'etichetta che conta ai fini di tracciabilità, distinta dal riepilogo scatolone e dall'etichetta ufficiale del corriere (DHL/BRT)
- Test di non regressione: confronto output tra endpoint e prototipo su `ordini_esempio.csv`

Dipendenze: nessuna esterna. Bloccante per tutti gli sprint successivi.

## Sprint 2 — Macchina a stati spedizione + adapter corriere (bozza)

Obiettivo: introdurre lo stato "bozza spedizione" nel dominio Shipping e il primo adapter corriere funzionante end-to-end in modalità draft.

- ~~Modellare la FSM `bozza → confermata → ritirata`~~ — fatto: tabella `viscotta.spedizioni` creata sul DB reale (`sql/spedizioni_fsm.sql`, eseguita a mano il 31/08/2026). Workflow implementato: `POST /spedizioni` crea bozza (solo quotazione, nessun effetto reale) → `POST /spedizioni/{id}/conferma` (effetto reale: crea spedizione+etichetta) → `POST /spedizioni/{id}/pickup` (effetto reale: prenota ritiro). Mai invio automatico diretto: ogni transizione con effetto reale richiede una chiamata esplicita. Testato end-to-end con TestClient su un ordine reale (`ORD-20260723-5969`): la bozza si crea, la conferma fallisce correttamente in stato `fallita` se il cliente non ha telefono in anagrafica (DHL lo richiede obbligatoriamente per `/shipments`) — vedi punto aperto sotto
- Adapter BRT (ha un flusso draft nativo: `createShipment` provvisoria → `confirmShipment`/`deleteShipment`) — non ancora iniziato, resta da fare
- Interfaccia comune "corriere" dietro cui BRT e (in seguito) DHL sono intercambiabili — non ancora fatto (oggi la FSM parla solo con `app/dhl.py` direttamente)
- ~~Endpoint `POST /spedizioni` ... `DELETE /spedizioni/{id}`~~ — fatto, più `GET /spedizioni/{id}`, `GET /spedizioni/{id}/etichetta`, `POST /spedizioni/{id}/pickup` (non previsti nel piano originale, aggiunti per lo scope pickup confermato da Alessandro)
- ~~Adapter DHL MyDHL~~ — fatto: tutte e tre le chiamate (`/rates`, `/shipments`, `/pickups`) implementate e testate con successo, prima in ambiente `exp-mydhlapi-sandbox-all-m` poi (31/08/2026) in **produzione** — Alessandro Menna ha verificato le chiamate di test e abilitato l'account `127990547`. `DHL_API_BASE_URL` ora punta a produzione, stesse credenziali

Dipendenze: nessuna aperta — account `127990547` abilitato in produzione su MyDHL API il 31/08/2026. **Da qui in poi `crea_spedizione`/`richiedi_pickup` hanno sempre effetto reale** (costo reale, ritiro reale) — non richiamarle mai per prova, solo per un ordine vero.

Punto aperto emerso dal test end-to-end: **molti clienti non hanno il telefono in anagrafica** (`viscotta.customers.phone`), campo obbligatorio per DHL su `/shipments` — la conferma di una spedizione fallisce (stato `fallita`, non un bug) per quei clienti finché il dato non viene integrato. **Mitigato**: `fetch_destinatario` (`shipping-api/app/db.py`) ora fa fallback su `easyfatt.tanagrafica.tel`/`cell`, agganciata via `codanagr = customers.code` (chiave pulita, nessun duplicato) — recupera il telefono per 49 dei 106 clienti attivi che ne erano privi nel Portal. Restano senza telefono in nessuna delle due fonti gli altri ~57: per quelli la conferma continuerà a fallire finché il dato non viene integrato a mano o richiesto obbligatorio sul Portal.

## Sprint 3 — Etichette con lotto reale ed endpoint operativo (avvio Fase 2)

Obiettivo: spostare la generazione etichette a valle della produzione, con lotto/scadenza reali, e dare al reparto un endpoint per confermare i colli in produzione.

- ~~Recuperare lotto/scadenza dalle tabelle miniMRP~~ — **corretto in corsa**: `viscotta.ordini_produzione` (miniMRP) non ha lotto/scadenza strutturati (`lotto_label` contiene in realtà l'order_number). Il dato reale vive in `easyfatt.tmovmagazz` (gestionale): si produce fresco su ordine, quindi l'ultimo movimento di carico (`qtacaricata`) per lo SKU è il lotto giusto — niente FEFO su giacenza aggregata. Implementato: `db.fetch_ultimo_lotto(sku)`
- ~~Stampa a fine linea delle etichette **collo interno** (WP50/WP40) con lotto/scadenza reali~~ — fatto, `GET /cartonizzazioni/{order_number}/etichette-colli` ora stampa lotto/scadenza reali da EasyFatt invece del placeholder
- ~~Etichetta scatolone (riepilogo interno) con dati reali~~ — fatto: `GET /cartonizzazioni/{order_number}/etichette-scatolone`, stesso formato/stampante 15×10 cm orizzontale delle etichette collo (decisione col reparto, 04/09/2026), una pagina per scatolone, cliente/data consegna reali da `db.fetch_order` (ora include `requested_delivery_date`), riepilogo contenuto+pesi, non censiti segnalati sull'ultimo scatolone. Resta comunque distinta dall'etichetta ufficiale del corriere
- ~~Endpoint per il reparto: conferma collo/scansione a fine linea~~ — fatto: `POST /cartonizzazioni/colli/conferma` (body `{"codice": "<ordine>-NN"}`, stesso testo già codificato nel barcode dell'etichetta scatolone — si scansiona il barcode già stampato, nessuna digitazione), `GET /cartonizzazioni/{order_number}/colli` (stato: confermati/mancanti/completo), `DELETE /cartonizzazioni/{order_number}/colli/{indice_collo}` (annulla, errore di scansione). Idempotente per doppia scansione. Tabella `viscotta.colli_confermati` in `sql/colli_confermati.sql`, eseguita sul DB reale il 04/09/2026
- ~~Gate: bloccare la conferma spedizione se mancano colli scansionati~~ — fatto: `POST /spedizioni/{id}/conferma` ora rifiuta con 409 se `GET .../colli` non è `completo` (mancherebbero colli scansionati) — prima non c'era alcun controllo incrociato tra le due FSM, si poteva confermare una spedizione reale (costo reale, ritiro reale) anche con uno scatolone ancora aperto sul tavolo
- ~~Generare il contratto OpenAPI da FastAPI e il client TS derivato~~ — fatto: `shipping-api/scripts/export_openapi.py` scrive `client-ts/openapi.json` dalle sole firme dei router (nessuna chiamata DB/DHL); `client-ts/` genera i tipi con `openapi-typescript` e un thin client tipizzato con `openapi-fetch` (`npm run refresh` per rigenerare dopo una modifica). Non ancora consumato da nessuno (`shipping-web` non esiste): contratto pronto in anticipo, client volutamente minimale finché non c'è un vero consumatore
- ~~Caso limite `fetch_ultimo_lotto`: produzione multipla dello stesso SKU nello stesso giorno per ordini diversi~~ — **non è un rischio**: confermato che il lotto è unico per data+prodotto, tutti gli ordini che spediscono lo stesso prodotto lo stesso giorno condividono legittimamente lo stesso lotto. Il vincolo reale trovato in corsa è un altro: `easyfatt.tmovmagazz` è scritta dall'**ETL EasyFatt → BI (`bi.viscotta.com`), lanciato a mano, senza orario fisso** — nessuna etichetta con lotto reale è affidabile prima che l'ETL sia stato rilanciato quel giorno. Dato che il lotto è unico per giornata (non serve tempo reale), basta farlo girare **una volta a fine turno di produzione**, prima di stampare le etichette. Sequenza completa in `procedura-giorno-produzione.md`. Rete di sicurezza a basso costo, non urgente: far fallire esplicitamente `GET /cartonizzazioni/{order_number}/etichette-colli` se l'ultimo carico trovato non è del giorno atteso, invece di stampare in silenzio il lotto di un giorno precedente

Dipendenze: Sprint 2 completato (FSM spedizione); accesso in lettura alle tabelle miniMRP rilevanti.

## Sprint 4 — `shipping-web` MVP

Obiettivo: prima interfaccia operativa di reparto, sostituendo l'uso diretto di `cartonize.py` da riga di comando.

- ~~Scaffold `shipping-web/` (TS/React), client generato dall'OpenAPI di `shipping-api`~~ — fatto: Next.js 16 (App Router, TypeScript, Tailwind), stesso stack/pattern di deploy del Portal. `@viscotta/shipping-client` collegato come dipendenza locale (`file:../client-ts`, symlink npm); `turbopack.root` puntato alla directory padre del repo e `transpilePackages` aggiunto per risolvere il pacchetto locale non pre-compilato (necessari entrambi, non solo uno — verificato con `npm run build`, non solo `next dev`). Home page: health check reale end-to-end (browser → Next.js server → shipping-api → DB), verificato con entrambi i servizi in esecuzione in locale. `main.py` `/health` ha ora un `response_model` esplicito (mancava, il client tipizzato altrimenti vede `{}`)
- ~~Vista lista ordini da spedire con stato (bozza/confermata/ritirata)~~ — fatto, **solo lettura** (nessuna azione dalla UI, deliberatamente: si passa all'operatività reale solo la settimana dell'11/09/2026). Nuovo endpoint `GET /spedizioni/elenco` (`data_da`/`data_a`, default oggi+13 giorni): per ogni ordine "in prenotazione" nel periodo, colli confermati/totali e stato spedizione più recente (`non_iniziata` se non esiste ancora una bozza). Pagina `shipping-web` `/spedizioni`, tabella con badge di stato colorati, verificata con dati reali dal DB condiviso
- Azione di conferma spedizione e stampa etichetta dalla UI
- Autenticazione/permessi coerenti con l'Order Portal (stesso modello RBAC admin/agent/customer, o sottoinsieme rilevante per il reparto)

Dipendenze: Sprint 3 completato (contratto OpenAPI stabile).

## Sprint 5 — Hardening e rollout

Obiettivo: passare da MVP funzionante a servizio affidabile in produzione.

- Gestione errori corriere (timeout, rifiuto indirizzo, retry) e stato "fallita" nella FSM
- Log/audit delle spedizioni per troubleshooting
- Validazione finale di tutte le pesature reali (colli `derivato` → censiti)
- Deploy in produzione secondo la strategia sotto (già preparata per `shipping-api` allo Sprint 1: `Dockerfile`, `ecs-task-definition.template.json`)

Dipendenze: Sprint 4 completato.

---

## Strategia di deploy AWS

Stesso account AWS (`025066246989`, `eu-central-1`) e stesso RDS condiviso (`database-hai...rds.amazonaws.com`) degli altri tre componenti VISCOTTA. Pattern verificati sui repo reali:

| Componente | Stack | Deploy |
|---|---|---|
| Order Portal | Next.js/TS | **AppRunner** source-based (`AppRunner.yaml`, `npm run build`/`npm start`), porta 3000, health `/api/health` |
| miniMRP | Python/Streamlit | **Docker → ECR → ECS Fargate**, porta 8501, secrets da **SSM Parameter Store**, log CloudWatch |
| BI/Metabase | immagine ufficiale Metabase | **ECS Fargate**, porta 3000, secrets da **Secrets Manager** |
| ETL BI | Python | non in cloud — gira su scheduler Windows di un desktop lab (nota aperta, fuori scope Shipping) |

Decisione per Shipping:

- **`shipping-api`** (Python/FastAPI) → stesso pattern di **miniMRP**: Docker → ECR → ECS Fargate. Preparati allo Sprint 1: `shipping-api/Dockerfile` (build e healthcheck verificati in locale), `shipping-api/ecs-task-definition.template.json` (family `viscotta-shipping-api`, porta 8000, `DATABASE_URL` da SSM `/viscotta/shipping-api/DATABASE_URL`, log group `/ecs/viscotta-shipping-api`).
- **`shipping-web`** (TS/React, Sprint 4) → stesso pattern del **Portal**: AppRunner source-based, nessun Docker/ECS.

Da fare quando si passa al deploy reale (fuori scope finché non ci sono ambienti AWS dedicati): creare repo ECR `viscotta-shipping-api`, ruolo IAM `viscotta-shipping-api-task-role`, parametro SSM con la connection string reale, servizio ECS + load balancer/target group.

---

## Rischi e punti aperti che condizionano la sequenza

| Punto aperto | Impatto | Sprint interessato |
|---|---|---|
| ~~Credenziali MyDHL API + account number non disponibili~~ — arrivate, app in produzione dal 31/08/2026 | Risolto | Sprint 2 |
| ~~Tara e dimensioni reali dello scatolone da pesare~~ — pesata 27/08/2026: 250 g | Risolto | Sprint 1 |
| Pesature dei colli marcati `derivato` | Alcuni pesi restano "da verificare" in etichetta | Sprint 1, Sprint 5 |
| SKU definitivi scatole regalo/Natale | Cartonizzazione di quei prodotti resta incompleta | Sprint 1 |
| ~~Conferma stato ordine "in prenotazione"~~ — confermato: `status = 'submitted'` E `crm_opportunity_id IS NOT NULL` (deve esistere l'Opportunity in CRM, non basta il submit sul Portal — 18 ordini storici erano `submitted`/`crm_export_status='exported'` ma senza Opportunity) | Risolto | Sprint 1 |
| Team produzione+packaging+spedizione condiviso (3 persone) | Il coordinamento implicito oggi va reso esplicito nel sistema — impatta UX di Sprint 4 | Sprint 4 |
| ~~App developer.dhl.com in stato "pending"~~ — sbloccata da Alessandro Menna, poi promossa a produzione il 31/08/2026 | Risolto | Sprint 2 |
| ~~Caso limite `fetch_ultimo_lotto`: produzione multipla dello stesso SKU nello stesso giorno per ordini diversi~~ — confermato: il lotto è unico per data+prodotto, condiviso legittimamente tra ordini | Non era un rischio reale | Sprint 3 |
| `easyfatt.tmovmagazz` è scritta dall'ETL EasyFatt→BI, lanciato a mano senza orario fisso — l'etichetta lotto non è affidabile se richiesta prima che l'ETL sia stato rilanciato quel giorno (vedi `procedura-giorno-produzione.md`) | Rischio di lotto vecchio o mancante in etichetta, silenzioso — mitigazione: owner+orario fisso per l'ETL a fine turno produzione (basta una volta al giorno, il lotto non serve in tempo reale) | Sprint 3 |
| ~~Molti clienti senza telefono in anagrafica (`viscotta.customers.phone`)~~ — mitigato: fallback su `easyfatt.tanagrafica` via `codanagr = customers.code`, recupera 49/106 casi | Restano ~57 clienti senza telefono in nessuna delle due fonti — `conferma` fallisce ancora per quelli. **Verificato (31/08/2026)**: nel periodo 01/09–30/11/2026 solo 1 di questi 57 ha un ordine "in prenotazione" (STREGATE TEA SHOP, ORD-20260613-9021, consegna 29/10) — **risolto**: telefono trovato sul portale MyDHL+ e inserito (`051 222 564`). Gli altri 56 possono restare senza numero per ora | Sprint 2 |
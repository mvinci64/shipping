# Shipping — Piano sprint

Piano di sviluppo a sprint per portare il dominio spedizioni da prototipo (`prototype/cartonize.py`) a servizio in produzione, secondo il percorso a fasi definito in `valutazione-cartonizzazione.md` (Fase 0 fatta, Fase 1 in corso, Fase 2/3 da avviare).

Contesto: il sistema informativo VISCOTTA comprende quattro progetti, ciascuno con Claude Code — Order Portal (TS, IDEA), miniMRP (Python, PyCharm), BI (Python, PyCharm), Shipping (questo repo). Shipping dipende dal Portal per anagrafica clienti/ordini e dal miniMRP per lotto/scadenza a fine linea; non li modifica.

Durata sprint indicativa: 2 settimane. Le stime vanno adattate al fatto che oggi produzione+packaging+spedizione sono le stesse 3 persone.

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

- ~~Modellare la FSM `bozza → confermata → ritirata`~~ — fatto: tabella `viscotta.spedizioni` (DDL in `sql/spedizioni_fsm.sql`, **da eseguire manualmente sul DB reale**, non ancora fatto — modifica strutturale su DB condiviso, eseguita a mano per scelta). Workflow implementato: `POST /spedizioni` crea bozza (solo quotazione, nessun effetto reale) → `POST /spedizioni/{id}/conferma` (effetto reale: crea spedizione+etichetta) → `POST /spedizioni/{id}/pickup` (effetto reale: prenota ritiro). Mai invio automatico diretto: ogni transizione con effetto reale richiede una chiamata esplicita
- Adapter BRT (ha un flusso draft nativo: `createShipment` provvisoria → `confirmShipment`/`deleteShipment`) — non ancora iniziato, resta da fare
- Interfaccia comune "corriere" dietro cui BRT e (in seguito) DHL sono intercambiabili — non ancora fatto (oggi la FSM parla solo con `app/dhl.py` direttamente)
- ~~Endpoint `POST /spedizioni` ... `DELETE /spedizioni/{id}`~~ — fatto, più `GET /spedizioni/{id}`, `GET /spedizioni/{id}/etichetta`, `POST /spedizioni/{id}/pickup` (non previsti nel piano originale, aggiunti per lo scope pickup confermato da Alessandro)
- ~~Adapter DHL MyDHL~~ — fatto: tutte e tre le chiamate (`/rates`, `/shipments`, `/pickups`) implementate, testate con successo in ambiente `exp-mydhlapi-sandbox-all-m` e agganciate alla FSM

Dipendenze: account `127990547` abilitato in produzione su MyDHL API (richiesta inviata ad Alessandro Menna il 31/08/2026, in attesa) — ambiente test già attivo e funzionante nel frattempo. DDL `spedizioni_fsm.sql` da eseguire manualmente prima che gli endpoint `/spedizioni` funzionino.

## Sprint 3 — Etichette con lotto reale ed endpoint operativo (avvio Fase 2)

Obiettivo: spostare la generazione etichette a valle della produzione, con lotto/scadenza reali, e dare al reparto un endpoint per confermare i colli in produzione.

- ~~Recuperare lotto/scadenza dalle tabelle miniMRP~~ — **corretto in corsa**: `viscotta.ordini_produzione` (miniMRP) non ha lotto/scadenza strutturati (`lotto_label` contiene in realtà l'order_number). Il dato reale vive in `easyfatt.tmovmagazz` (gestionale): si produce fresco su ordine, quindi l'ultimo movimento di carico (`qtacaricata`) per lo SKU è il lotto giusto — niente FEFO su giacenza aggregata. Implementato: `db.fetch_ultimo_lotto(sku)`
- ~~Stampa a fine linea delle etichette **collo interno** (WP50/WP40) con lotto/scadenza reali~~ — fatto, `GET /cartonizzazioni/{order_number}/etichette-colli` ora stampa lotto/scadenza reali da EasyFatt invece del placeholder
- Etichetta scatolone (100×150, riepilogo interno) con dati reali, resta comunque distinta dall'etichetta ufficiale del corriere
- Endpoint per il reparto: conferma collo/scansione a fine linea, aggiornamento stato spedizione
- Generare il contratto OpenAPI da FastAPI e il client TS derivato (per uso da `shipping-web` e potenzialmente dal Portal)

Dipendenze: Sprint 2 completato (FSM spedizione); accesso in lettura alle tabelle miniMRP rilevanti.

## Sprint 4 — `shipping-web` MVP

Obiettivo: prima interfaccia operativa di reparto, sostituendo l'uso diretto di `cartonize.py` da riga di comando.

- Scaffold `shipping-web/` (TS/React), client generato dall'OpenAPI di `shipping-api`
- Vista lista ordini da spedire con stato (bozza/confermata/ritirata)
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
| Credenziali MyDHL API + account number non disponibili | Adapter DHL rimandabile, si parte da BRT | Sprint 2 |
| ~~Tara e dimensioni reali dello scatolone da pesare~~ — pesata 27/08/2026: 250 g | Risolto | Sprint 1 |
| Pesature dei colli marcati `derivato` | Alcuni pesi restano "da verificare" in etichetta | Sprint 1, Sprint 5 |
| SKU definitivi scatole regalo/Natale | Cartonizzazione di quei prodotti resta incompleta | Sprint 1 |
| ~~Conferma stato ordine "in prenotazione"~~ — confermato: `status = 'submitted'` E `crm_opportunity_id IS NOT NULL` (deve esistere l'Opportunity in CRM, non basta il submit sul Portal — 18 ordini storici erano `submitted`/`crm_export_status='exported'` ma senza Opportunity) | Risolto | Sprint 1 |
| Team produzione+packaging+spedizione condiviso (3 persone) | Il coordinamento implicito oggi va reso esplicito nel sistema — impatta UX di Sprint 4 | Sprint 4 |
| App developer.dhl.com in stato "pending" — nessuna produzione, ne sandbox funzionanti | `/spedizioni/valida` non chiamabile (401 sia in produzione che sandbox) | Sprint 2 |
| Caso limite `fetch_ultimo_lotto`: produzione multipla dello stesso SKU nello stesso giorno per ordini diversi | Rischio di stampare il lotto di un altro ordine se non è davvero sempre "ultimo carico = questo ordine" — da verificare con chi segue EasyFatt | Sprint 3 |
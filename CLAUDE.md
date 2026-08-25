# CLAUDE.md — Progetto Shipping (VISCOTTA)

Contesto per Claude Code. Questo repo è il sistema di **cartonizzazione e spedizione** di VISCOTTA, azienda di prodotti da forno artigianali (chips di mandorla, grissini, cantucci, torte capresi...). Lingua di lavoro: italiano.

## Il sistema informativo VISCOTTA

Tre applicazioni esistenti, più questo progetto:

- **Order Portal** (app.viscotta.com) — TypeScript. Riceve ordini/prenotazioni da clienti e agenti. DB: schema `viscotta` (tabelle `products`, `orders`, `order_items`, `customers` con `company_name`).
- **miniMRP** — Python. Piano di produzione per lotti giornalieri. Tabelle: `viscotta.prodotti` (con `lotto_minimo`, `lotto_ottimale`), `ordini_produzione`, `v_lotti_giorno`.
- **BI** — ETL + Metabase. Schemi: `viscotta`, `easyfatt` (gestionale), `reviso` (contabilità), `bi`.
- **Shipping** (questo repo) — il nuovo dominio spedizioni.

## Decisione architetturale chiave (vedi valutazione-cartonizzazione.md)

La cartonizzazione è un dominio di **spedizione**: la sede operativa è a valle del miniMRP (dove il lotto è noto — le etichette DEVONO riportare lotto/scadenza), l'anagrafica configurazioni vive nel DB del Portal, la BI serve per simulare/validare. Percorso a fasi:

- **Fase 0 (fatta)**: kit read-only Metabase in `sql/bi/` (Q1–Q6, candidate in CTE VALUES).
- **Fase 1 (in corso)**: anagrafica configurazioni (`sql/anagrafica_configurazioni.sql` + `sql/fase1_seed_censimento.sql`) e prototipo `prototype/cartonize.py`.
- **Fase 2**: modulo operativo a valle del miniMRP, stampa etichette con lotto a fine linea.
- **Fase 3**: app dedicata, se/quando servono corrieri multipli, SSCC, EDI.

## Stack: Python e TypeScript NELLO STESSO PROGETTO

Decisione presa e da mantenere: **backend Python (FastAPI) + frontend TypeScript (React), stesso repo/progetto IDEA** (IntelliJ IDEA Ultimate + plugin Python, interprete nella venv `./venv`).

- `shipping-api/` (futuro) — Python/FastAPI. Gemma dal prototipo; contigua al miniMRP (Python), tiene aperta la porta a OR-Tools per colli misti.
- `shipping-web/` (futuro) — TS/React. UI operativa di reparto (scanner, stati collo, stampa).
- Contratto tra i due mondi: **OpenAPI generata da FastAPI** → client TS tipizzati (anche per il Portal).
- Le spedizioni sono **sempre 1:1 con gli ordini** (confermato): niente consolidamenti/parziali.

## Regole di dominio (censimento imballi del 26/08, fonte: Vincenza + squadra packaging)

- Scatole interne: **WP50** (tara 200 g, occupa 2 posti) e **WP40** (tara 150 g, 1 posto).
- **Scatolone VISCOTTA = 6 posti** (3×WP50 o 6×WP40 o mix). Tara stimata 400 g — DA PESARE.
- Prodotti standard (CHMS50, GRM100, CANTS100, CMEN080, MCIOC080, MSAL080): 24 pz → WP50, 12 pz → WP40. TCAP075: 12 → WP50, 6 → WP40. CANT200/BRUT150/VP08BUST: 12 → WP50, 6 → WP40 (pesi collo censiti). BOXOV/SCAT20V08: solo WP40 da 6 (220 g/pezzo). Scatole regalo/Natale: 6 → WP40 (SKU da confermare).
- Ottimizzazione: prima WP50 pieni, resto in WP40; prodotti non censiti negli spazi liberi dell'ultimo scatolone.
- Il **quanto di imballo** è anche vincolo del piano di produzione (miniMRP): lotti arrotondati a colli pieni (viste V6/V7). Oggi produzione+packaging+spedizione = stesse 3 persone; domani squadre separate → il coordinamento implicito va reso esplicito nel sistema.

## Corrieri

- **DHL Express (MyDHL API)**: nessun vero stato draft; si emula con il flusso di validazione (dati senza emissione etichetta) e creazione reale alla conferma. Basic Auth, credenziali dal referente DHL — NON ANCORA DISPONIBILI.
- **BRT**: API REST con flusso draft nativo (createShipment provvisoria → confirmShipment/deleteShipment). Documentazione dal commerciale BRT, non pubblica.
- Design: stato "bozza spedizione" nel NOSTRO dominio (macchina a stati bozza→confermata→ritirata), corrieri come adapter dietro interfaccia comune.

## Stato attuale e prossimi passi

Fatto: valutazione architetturale (docx in `docs/` — la copia in docs/ è il MASTER, modificata a mano, non rigenerarla da script), DDL validato su PostgreSQL 16, kit BI operativo su schema reale, prototipo eseguibile (`prototype/cartonize.py`: CSV ordini → scatoloni → pesi → etichette PDF 100×150 → payload draft MyDHL).

Mancano per la produzione: credenziali MyDHL API + account number; indirizzi cliente da `viscotta.customers`; tara e dimensioni reali scatolone; pesate dei colli marcati `derivato` (vista `vw_peso_confezione` / dizionario `CONFEZIONI` in cartonize.py); SKU definitivi scatole regalo/Natale; verifica stato ordine "in prenotazione" (oggi filtro `status = 'submitted'` in Q6, da confermare).

Prossimo sviluppo concordato: trasformare `prototype/cartonize.py` nel primo endpoint di `shipping-api` (FastAPI) con chiamata di validazione DHL reale, appena arrivano le credenziali.

## Convenzioni

- SQL: PostgreSQL 16, snake_case italiano per il dominio nuovo (`configurazione_collo`), nomi reali inglesi per le tabelle del Portal. Ogni query/DDL va validata su un'istanza reale prima della consegna.
- Le query BI sono SOLO SELECT: mai DDL sul DB della BI.
- Documenti per il team di produzione: linguaggio semplice, zero tecnicismi (vedi `docs/VISCOTTA_scatoloni_per_il_laboratorio.docx`).
- Pesi in grammi negli schemi, kg nelle etichette/UI. Il peso "ufficiale" è la pesata censita quando esiste (`peso_collo_noto_g`), altrimenti derivato da grammatura+tara e marcato da verificare.

# Shipping — Configurazioni standard di imballo e cartonizzazione

**Valutazione architetturale: dove collocare la funzionalità**

Sistema informativo VISCOTTA — Order Portal · miniMRP · BI
Redatto per: Ing. Marcello Vinci — 15 agosto 2026 — Bozza per discussione interna

---

## Indice

- [1. Contesto e obiettivo](#1-contesto-e-obiettivo)
- [2. Il dominio funzionale: la cartonizzazione](#2-il-dominio-funzionale-la-cartonizzazione)
- [3. Valutazione delle opzioni](#3-valutazione-delle-opzioni)
- [4. Raccomandazione: un percorso a fasi](#4-raccomandazione-un-percorso-a-fasi)
- [Appendice A — Modello dati dell'anagrafica configurazioni](#appendice-a--modello-dati-dellanagrafica-configurazioni)
- [Appendice B — Viste per la BI (Metabase)](#appendice-b--viste-per-la-bi-metabase)

---

## 1. Contesto e obiettivo

Il sistema informativo VISCOTTA è oggi articolato su tre applicazioni: l'**Order Portal** (app.viscotta.com), che riceve ordini e prenotazioni da clienti e agenti; il **miniMRP**, che genera il piano di produzione per lotti giornalieri; la piattaforma di **Business Intelligence** (ETL e Metabase) per l'analisi dei dati.

Si vuole introdurre la gestione delle configurazioni standard di imballo: ogni scatolone siglato (es. VISCOTTA, tara nota in grammi) contiene un numero definito di scatole interne (es. 3 × WP50, tara nota) ciascuna con un numero definito di pezzi (es. 24 chips, per un totale di 72), con peso lordo nominale noto (~6,1 kg). Ogni ordine della lista prenotazioni deve essere spedito; ogni prodotto ha il proprio imballo interno; le combinazioni devono essere assegnate agli scatoloni, ottimizzate ed etichettate di conseguenza.

Il presente documento valuta le quattro collocazioni possibili della funzionalità, ne confronta fattibilità, pro e contro, e propone un percorso di adozione. L'Appendice A definisce il modello dati dell'anagrafica configurazioni (DDL PostgreSQL); l'Appendice B le viste SQL per la BI.

## 2. Il dominio funzionale: la cartonizzazione

L'assegnazione di righe d'ordine a configurazioni standard di collo, con relativa ottimizzazione ed etichettatura, è nota in letteratura come **cartonizzazione** (*cartonization*). È concettualmente un dominio di **spedizione**, non di ordini né di produzione: questo è il criterio che orienta l'intera valutazione.

La domanda chiave è: *quando si conosce la verità fisica di ciò che parte nello scatolone?* Al momento dell'ordine si conosce ciò che il cliente vuole (packaging teorico); a fine linea si conosce ciò che è stato prodotto e in quale lotto; alla spedizione si conosce ciò che parte davvero. Ogni opzione colloca la funzionalità in uno di questi tre momenti, con conseguenze diverse sulla correttezza delle etichette e sulla flessibilità operativa.

Un secondo criterio, spesso decisivo nel settore alimentare: se le etichette dei colli devono riportare **lotto, data di produzione o scadenza**, l'etichettatura non può che avvenire a valle della produzione, dove il lotto è noto.

## 3. Valutazione delle opzioni

### 3.1 Opzione 1 — Order Portal (app.viscotta.com)

La cartonizzazione viene calcolata all'accettazione dell'ordine, con generazione delle etichette in PDF; l'anagrafica dei parametri è un nuovo sprint del portale.

| Pro | Contro |
|---|---|
| Costo minimo: un solo sprint, anagrafica semplice, nessuna nuova applicazione. | Le etichette generate all'accettazione sono teoriche: lotto, data di produzione e scadenza non esistono ancora — quasi certamente richiesti per un prodotto alimentare. |
| Packaging teorico disponibile subito: si può comunicare al cliente il numero di colli e suggerire l'arrotondamento delle quantità a scatoloni pieni (ottimizzazione a monte, di grande valore commerciale). | Non gestisce modifiche d'ordine, spedizioni parziali, consolidamento di più ordini in una spedizione. |
| Il DB del portale è la sede naturale dell'anagrafica prodotti: le configurazioni vi si agganciano bene. | Rischio di stampare etichette che in magazzino non corrispondono alla realtà fisica. Il portale, nato per la raccolta ordini, inizierebbe a inglobare logica di fulfillment (*scope creep*). |

### 3.2 Opzione 2 — miniMRP

La cartonizzazione avviene a valle della catena di produzione: i lotti appena prodotti e confezionati trovano posto negli scatoloni direttamente a fine linea.

| Pro | Contro |
|---|---|
| È il punto più vicino alla realtà fisica: a valle del confezionamento sono noti lotto, quantità reali e peso reale. | Il miniMRP ragiona per lotti di produzione, non per ordini/spedizioni: dovrebbe conoscere il mondo delle prenotazioni. |
| Le etichette stampate qui sono vere, con tracciabilità di lotto integrata — requisito quasi obbligato nell'alimentare. | Un ordine può attingere da più lotti o da stock a scaffale; una spedizione può aggregare più ordini: casi che il piano lotti da solo non copre. |
| Flusso naturale: lotto prodotto → confezionato → cartonizzato → etichettato. Possibile controllo peso a fine linea contro il peso nominale della configurazione (± tolleranza). | *Scope creep*: da pianificatore diventa mezzo sistema di fulfillment, da governare con un perimetro di modulo ben definito. |

### 3.3 Opzione 3 — Query Metabase (BI)

A bocce ferme, una serie di query e dashboard Metabase calcola le combinazioni e l'assegnazione ottimale sui dati consolidati.

| Pro | Contro |
|---|---|
| Costo quasi nullo e rischio zero: nessuna modifica alle applicazioni operative. | Read-only e non transazionale per definizione: nessun workflow, nessuno stato (collo preparato? spedito?). |
| Perfetta per simulare: quante configurazioni standard servono davvero, saturazione media degli scatoloni sugli ordini storici, casi limite. | Nessuna stampa etichette operativa, nessun barcode, nessuna integrazione con la linea. |
| Strumento ideale per progettare e validare lo standard prima di implementarlo (le viste dell'Appendice B nascono per questo). | Non può essere la sede operativa della funzionalità: è un ottimo passo zero, non l'approdo. |

### 3.4 Opzione 4 — Applicazione logistica dedicata

Il tema diventa il seme di un sistema informativo di logistica: una quarta applicazione che legge ordini dal Portal e lotti dal miniMRP e governa colli e spedizioni.

| Pro | Contro |
|---|---|
| Architettura pulita: la spedizione è un dominio a sé; nessun sistema esistente viene appesantito. | Costo massimo: quarta applicazione da sviluppare e mantenere (autenticazione, integrazioni, deploy, backup). |
| Spazio di crescita naturale: picking, packaging list, DDT, etichette SSCC/GS1-128, integrazione corrieri, EDI con la GDO. | Overhead di integrazione con entrambi i sistemi esistenti fin dal primo giorno. |
| Confini chiari: legge ordini e lotti, scrive colli e spedizioni. | Con volumi contenuti rischia di essere sovradimensionata: una cattedrale per un problema da cappella. |

### 3.5 Sintesi comparativa

| Opzione | Costo | Rischio | Adeguatezza funzionale | Verdetto |
|---|---|---|---|---|
| 1. Order Portal | Basso (uno sprint) | Medio | Parziale: packing teorico, senza lotto/scadenza | Solo per il packing previsto |
| 2. miniMRP | Medio | Basso | Alta: a valle del confezionamento, lotto noto | **Consigliata come sede operativa** |
| 3. Metabase / BI | Molto basso | Nullo | Solo analisi, non operativa | **Consigliata come passo zero** |
| 4. App dedicata | Alto | Medio-alto | Massima, ma sovradimensionata oggi | Evoluzione futura |

## 4. Raccomandazione: un percorso a fasi

Le quattro opzioni non sono realmente alternative: sono fasi di uno stesso percorso.

1. **Fase 0 — Analisi in Metabase (subito).** Con le viste dell'Appendice B, misurare sugli ordini storici quante configurazioni standard servono, la saturazione attesa degli scatoloni e i casi limite. Costa pochi giorni e fornisce i numeri per calibrare tutto il resto.
2. **Fase 1 — Anagrafica condivisa nel DB del Portal.** Le configurazioni (imballo esterno, imballi interni, pezzi, pesi, tolleranze) si definiscono una volta sola, nel DB del Portal — già anagrafica prodotti di fatto — e si espongono agli altri sistemi (Appendice A). Il Portal può da subito mostrare il packaging previsto all'accettazione e suggerire quantità a scatoloni pieni: è quasi gratis e riusa la stessa anagrafica.
3. **Fase 2 — Modulo operativo a valle del miniMRP.** Il calcolo operativo e la stampa etichette (con lotto) vanno dove avviene fisicamente l'incartonamento: un modulo leggero di confezionamento/spedizione a valle del miniMRP, con perimetro esplicito per contenere lo *scope creep*.
4. **Fase 3 — Eventuale app logistica dedicata (futuro).** Se e quando arriveranno corrieri multipli, SSCC, EDI, gestione giacenze, il modulo della Fase 2 diventa il seme da estrarre in un'applicazione logistica autonoma ("Shipping"). Non partirci ora.

### 4.1 L'ottimizzazione a monte: il quanto di imballo come vincolo di produzione

Esiste una transizione critica tra la chiusura dei lotti di produzione giornalieri (ddmmyy per prodotto) e la creazione delle etichette. Oggi produzione, packaging e spedizione sono svolti dalle stesse tre persone, e l'ottimizzazione avviene in modo implicito, nella testa di chi lavora. Se in futuro le fasi passeranno a squadre distinte, quel coordinamento implicito va sostituito da uno esplicito nel sistema: automatizzarlo ora significa aumentare la produttività dopo.

Il principio: il **quanto di imballo** — pezzi per confezione (es. 24 chips per WP50) e pezzi per collo pieno (72) — deve diventare un vincolo di arrotondamento del piano di produzione del miniMRP, accanto ai vincoli di capacità del laboratorio (forno, impastatrici per le Torte Capresi). Un fabbisogno di 200 pezzi lascerebbe 2 colli pieni e 56 pezzi orfani; il lotto "giusto" è 216, cioè 3 colli esatti, con un'eccedenza di 16 pezzi il cui costo va confrontato con quello dei colli incompleti (gestione resti, spazio, rietichettature).

Il modello dati dell'Appendice A riflette già questa esigenza: `pezzi_per_confezione` è parametrico per prodotto e imballo, con validità temporale — se il WP50 passa da 25 a 24 pacchetti si chiude la riga vecchia e se ne apre una nuova, senza toccare lo storico. Le viste V6 e V7 (Appendice B.4) espongono al miniMRP i multipli naturali di ogni prodotto e il lotto suggerito arrotondato a colli pieni: sono il ponte formale tra fine produzione ed etichettatura.

### 4.2 Domande decisive prima di partire

1. Le etichette dei colli devono riportare lotto e/o scadenza? **Sì** — e quindi l'opzione Portal da sola diventa molto meno difendibile.
2. Le spedizioni sono sempre 1:1 con gli ordini, o esistono parziali e consolidamenti? **Sì, sempre 1:1** — la complessità del modulo di Fase 2 si riduce sensibilmente.

### 4.3 Stack tecnologico (nota)

Contesto: Order Portal in TypeScript, miniMRP in Python. Per l'eventuale app dedicata (Fase 3): **backend Python** (FastAPI), perché gemma dal modulo di Fase 2 nel mondo miniMRP e tiene aperta la porta del solver (OR-Tools) per i colli misti; **frontend TypeScript/React**, come il Portal. Il contratto tra i mondi è l'API OpenAPI generata da FastAPI, da cui generare client TS tipizzati. Naming repo: `shipping-api` e `shipping-web`.

---

## Appendice A — Modello dati dell'anagrafica configurazioni

Dialetto: **PostgreSQL 16**. Lo schema è stato eseguito e verificato su un'istanza PostgreSQL 16.13: i dati di esempio riproducono esattamente il caso citato (scatolone VISCOTTA + 3 × WP50 da 24 chips = 72 pezzi, 6.100 g lordi). Le tabelle `prodotto`, `ordine` e `ordine_riga` si assumono già esistenti nel DB dell'Order Portal; i nomi vanno adattati allo schema reale.

Il modello si regge su quattro entità: `imballo` (anagrafica unica di scatoloni e scatole interne, con tara e dimensioni), `prodotto_confezione` (come un prodotto entra nel suo imballo interno: pezzi per confezione e peso netto, con validità temporale), `configurazione_collo` (lo scatolone standard, con peso lordo nominale, tolleranza e priorità di scelta) e `configurazione_collo_riga` (la composizione: quante confezioni di quale imballo interno, per quale prodotto).

> **Nota tecnica** — il vincolo `UNIQUE (id, tipo)` su `imballo` abilita il pattern della *FK qualificata*: le tabelle figlie referenziano la coppia (id, tipo) e garantiscono a livello di schema che un imballo ESTERNO non possa mai essere usato come interno, e viceversa.

### A.1 Anagrafica imballi

```sql
-- ============================================================
-- 1. IMBALLO — anagrafica di tutti gli imballi (esterni e interni)
-- ============================================================
CREATE TABLE imballo (
    id             SERIAL PRIMARY KEY,
    codice         VARCHAR(20)  NOT NULL UNIQUE,      -- es. 'VISCOTTA', 'WP50'
    descrizione    VARCHAR(200),
    tipo           VARCHAR(10)  NOT NULL CHECK (tipo IN ('ESTERNO','INTERNO')),
    tara_g         INTEGER      NOT NULL CHECK (tara_g >= 0),
    lunghezza_mm   INTEGER,
    larghezza_mm   INTEGER,
    altezza_mm     INTEGER,
    attivo         BOOLEAN      NOT NULL DEFAULT TRUE,
    creato_il      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    aggiornato_il  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Chiave composta (id, tipo): permette alle tabelle figlie di vincolare
-- via FK anche il TIPO di imballo referenziato (pattern "FK qualificata").
ALTER TABLE imballo ADD CONSTRAINT uq_imballo_id_tipo UNIQUE (id, tipo);
```

### A.2 Confezionamento prodotto

```sql
-- ============================================================
-- 2. PRODOTTO_CONFEZIONE — come un prodotto entra nel suo imballo
--    interno (es. 24 chips in una scatola WP50)
-- ============================================================
CREATE TABLE prodotto_confezione (
    id                    SERIAL PRIMARY KEY,
    prodotto_id           INTEGER NOT NULL REFERENCES prodotto(id),
    imballo_interno_id    INTEGER NOT NULL,
    tipo_imballo          VARCHAR(10) NOT NULL DEFAULT 'INTERNO'
                          CHECK (tipo_imballo = 'INTERNO'),
    pezzi_per_confezione  INTEGER NOT NULL CHECK (pezzi_per_confezione > 0),
    peso_netto_g          NUMERIC(8,1) NOT NULL CHECK (peso_netto_g > 0),
    valido_dal            DATE NOT NULL DEFAULT CURRENT_DATE,
    valido_al             DATE,
    -- la FK composta garantisce che l'imballo sia di tipo INTERNO
    FOREIGN KEY (imballo_interno_id, tipo_imballo)
        REFERENCES imballo (id, tipo),
    UNIQUE (prodotto_id, imballo_interno_id, valido_dal)
);
```

### A.3 Configurazioni di collo e composizione

```sql
-- ============================================================
-- 3. CONFIGURAZIONE_COLLO — lo "scatolone" standard
--    (es. VISCOTTA-3xWP50: scatolone VISCOTTA con 3 WP50, ~6,1 kg)
-- ============================================================
CREATE TABLE configurazione_collo (
    id                     SERIAL PRIMARY KEY,
    codice                 VARCHAR(30) NOT NULL UNIQUE,  -- 'VISCOTTA-3xWP50'
    descrizione            VARCHAR(200),
    imballo_esterno_id     INTEGER NOT NULL,
    tipo_imballo           VARCHAR(10) NOT NULL DEFAULT 'ESTERNO'
                           CHECK (tipo_imballo = 'ESTERNO'),
    peso_lordo_nominale_g  INTEGER,                      -- es. 6100
    tolleranza_peso_pct    NUMERIC(4,1) NOT NULL DEFAULT 5.0,
    priorita               INTEGER NOT NULL DEFAULT 100, -- min = preferita
    attivo                 BOOLEAN NOT NULL DEFAULT TRUE,
    creato_il              TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (imballo_esterno_id, tipo_imballo)
        REFERENCES imballo (id, tipo)
);

-- ============================================================
-- 4. CONFIGURAZIONE_COLLO_RIGA — composizione dello scatolone
-- ============================================================
CREATE TABLE configurazione_collo_riga (
    id                  SERIAL PRIMARY KEY,
    configurazione_id   INTEGER NOT NULL
                        REFERENCES configurazione_collo(id) ON DELETE CASCADE,
    imballo_interno_id  INTEGER NOT NULL,
    tipo_imballo        VARCHAR(10) NOT NULL DEFAULT 'INTERNO'
                        CHECK (tipo_imballo = 'INTERNO'),
    numero_confezioni   INTEGER NOT NULL CHECK (numero_confezioni > 0),
    -- NULL = configurazione generica (qualunque prodotto confezionato
    -- in questo imballo interno); valorizzato = configurazione dedicata
    prodotto_id         INTEGER REFERENCES prodotto(id),
    FOREIGN KEY (imballo_interno_id, tipo_imballo)
        REFERENCES imballo (id, tipo),
    UNIQUE NULLS NOT DISTINCT (configurazione_id, imballo_interno_id, prodotto_id)
);
```

### A.4 Dati di esempio

```sql
-- Esempio: scatolone VISCOTTA, 3 scatole WP50 da 24 chips, ~6,1 kg
INSERT INTO imballo (codice, descrizione, tipo, tara_g) VALUES
    ('VISCOTTA', 'Scatolone siglato VISCOTTA', 'ESTERNO', 400),
    ('WP50',     'Scatola interna WP50',       'INTERNO', 100);

INSERT INTO prodotto_confezione
    (prodotto_id, imballo_interno_id, pezzi_per_confezione, peso_netto_g)
VALUES (
    (SELECT id FROM prodotto WHERE codice = 'CHIP-CLASSIC'),
    (SELECT id FROM imballo  WHERE codice = 'WP50'),
    24, 1800.0            -- 24 chips, 1,8 kg netti a scatola (75 g/chip)
);

INSERT INTO configurazione_collo
    (codice, descrizione, imballo_esterno_id, peso_lordo_nominale_g)
VALUES (
    'VISCOTTA-3xWP50', 'Scatolone VISCOTTA con 3 WP50 (72 chips)',
    (SELECT id FROM imballo WHERE codice = 'VISCOTTA'), 6100
);

INSERT INTO configurazione_collo_riga
    (configurazione_id, imballo_interno_id, numero_confezioni, prodotto_id)
VALUES (
    (SELECT id FROM configurazione_collo WHERE codice = 'VISCOTTA-3xWP50'),
    (SELECT id FROM imballo WHERE codice = 'WP50'),
    3,
    (SELECT id FROM prodotto WHERE codice = 'CHIP-CLASSIC')
);
```

---

## Appendice B — Viste per la BI (Metabase)

Viste di sola lettura, pensate per Metabase (Fase 0) e riutilizzabili come base dell'API di cartonizzazione (Fase 2). Le prime due espandono l'anagrafica; le successive incrociano l'anagrafica con gli ordini storici; le ultime due (B.4) alimentano il piano di produzione. Nota: la divisione `quantita_pezzi / pezzi_totali` tra interi è intenzionale (quoziente = colli pieni; `%` = pezzi residui).

### B.1 Anagrafica espansa

```sql
-- V1. Configurazione "esplosa": pezzi totali e peso lordo teorico
CREATE VIEW vw_configurazione_espansa AS
SELECT
    cc.id                                   AS configurazione_id,
    cc.codice                               AS configurazione,
    ie.codice                               AS imballo_esterno,
    SUM(r.numero_confezioni)                AS confezioni_totali,
    SUM(r.numero_confezioni * pc.pezzi_per_confezione) AS pezzi_totali,
    ie.tara_g
      + SUM(r.numero_confezioni * (ii.tara_g + pc.peso_netto_g))
                                            AS peso_lordo_teorico_g,
    cc.peso_lordo_nominale_g,
    cc.tolleranza_peso_pct,
    cc.priorita
FROM configurazione_collo cc
JOIN imballo ie                  ON ie.id = cc.imballo_esterno_id
JOIN configurazione_collo_riga r ON r.configurazione_id = cc.id
JOIN imballo ii                  ON ii.id = r.imballo_interno_id
LEFT JOIN prodotto_confezione pc
       ON pc.prodotto_id = r.prodotto_id
      AND pc.imballo_interno_id = r.imballo_interno_id
      AND (pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE)
WHERE cc.attivo
GROUP BY cc.id, cc.codice, ie.codice, ie.tara_g,
         cc.peso_lordo_nominale_g, cc.tolleranza_peso_pct, cc.priorita;

-- V2. Configurazione preferita per prodotto (priorita minima)
CREATE VIEW vw_configurazione_prodotto AS
SELECT DISTINCT ON (r.prodotto_id)
    r.prodotto_id,
    e.configurazione_id,
    e.configurazione,
    e.pezzi_totali,
    e.peso_lordo_teorico_g
FROM configurazione_collo_riga r
JOIN vw_configurazione_espansa e ON e.configurazione_id = r.configurazione_id
WHERE r.prodotto_id IS NOT NULL
ORDER BY r.prodotto_id, e.priorita;
```

### B.2 Cartonizzazione prevista degli ordini

```sql
-- V3. Cartonizzazione prevista per riga d'ordine
CREATE VIEW vw_cartonizzazione_prevista AS
SELECT
    o.id                                    AS ordine_id,
    o.numero                                AS numero_ordine,
    o.data_consegna,
    p.codice                                AS prodotto,
    r.quantita_pezzi,
    cp.configurazione,
    cp.pezzi_totali                         AS pezzi_per_collo,
    r.quantita_pezzi / cp.pezzi_totali      AS colli_pieni,
    r.quantita_pezzi % cp.pezzi_totali      AS pezzi_residui,
    ROUND(100.0 * ((r.quantita_pezzi / cp.pezzi_totali) * cp.pezzi_totali)
                / r.quantita_pezzi, 1)      AS pct_in_colli_pieni,
    ROUND(CEIL(r.quantita_pezzi::numeric / cp.pezzi_totali)
      * cp.peso_lordo_teorico_g / 1000.0, 1) AS peso_spedizione_stimato_kg
FROM ordine o
JOIN ordine_riga r                 ON r.ordine_id = o.id
JOIN prodotto p                    ON p.id = r.prodotto_id
JOIN vw_configurazione_prodotto cp ON cp.prodotto_id = r.prodotto_id;
```

### B.3 KPI di saturazione e copertura

```sql
-- V4. Saturazione mensile per configurazione (KPI di dimensionamento)
CREATE VIEW vw_saturazione_configurazioni AS
SELECT
    cp.configurazione,
    date_trunc('month', o.data_consegna)::date          AS mese,
    COUNT(DISTINCT o.id)                                AS ordini,
    SUM(r.quantita_pezzi)                               AS pezzi_ordinati,
    SUM(r.quantita_pezzi / cp.pezzi_totali)             AS colli_pieni,
    SUM(r.quantita_pezzi % cp.pezzi_totali)             AS pezzi_fuori_collo,
    ROUND(100.0 * SUM((r.quantita_pezzi / cp.pezzi_totali) * cp.pezzi_totali)
                / NULLIF(SUM(r.quantita_pezzi), 0), 1)  AS saturazione_pct
FROM ordine_riga r
JOIN ordine o                      ON o.id = r.ordine_id
JOIN vw_configurazione_prodotto cp ON cp.prodotto_id = r.prodotto_id
GROUP BY cp.configurazione, date_trunc('month', o.data_consegna);

-- V5. Copertura anagrafica: prodotti senza confezione o configurazione
CREATE VIEW vw_copertura_prodotti AS
SELECT
    p.id,
    p.codice,
    p.descrizione,
    (pc.id IS NOT NULL)                  AS ha_confezione_interna,
    (cp.configurazione_id IS NOT NULL)   AS ha_configurazione_collo
FROM prodotto p
LEFT JOIN prodotto_confezione pc
       ON pc.prodotto_id = p.id
      AND (pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE)
LEFT JOIN vw_configurazione_prodotto cp ON cp.prodotto_id = p.id;
```

Esempio di output verificato (V3): un ordine da 300 pezzi produce 4 colli pieni, 12 residui, saturazione 96 %, 30,5 kg stimati; un ordine da 200 pezzi produce 2 colli pieni, 56 pezzi residui, saturazione 72 %, 18,3 kg. La vista V4 aggrega per mese: nel test, saturazione complessiva 86,4 % — è il KPI con cui in Fase 0 si decide se le configurazioni standard proposte reggono la domanda reale.

### B.4 Dal packing alla produzione: quanto di imballo e lotto suggerito

Queste due viste chiudono il cerchio della sezione 4.1: trasformano il fabbisogno ordini in lotti di produzione già arrotondati a colli pieni, pronti per essere letti dal miniMRP come vincolo di pianificazione accanto alla capacità del laboratorio.

```sql
-- V6. Quanto di imballo per prodotto (vincolo per il miniMRP)
--     I "multipli naturali" di ogni prodotto: pezzi per confezione
--     e pezzi per collo pieno.
CREATE VIEW vw_quanto_imballo_prodotto AS
SELECT
    pc.prodotto_id,
    pc.pezzi_per_confezione,
    cp.configurazione,
    cp.pezzi_totali        AS pezzi_per_collo
FROM prodotto_confezione pc
JOIN vw_configurazione_prodotto cp ON cp.prodotto_id = pc.prodotto_id
WHERE pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE;

-- V7. Lotto suggerito: fabbisogno per data di consegna arrotondato
--     per eccesso a colli pieni.
CREATE VIEW vw_lotto_suggerito AS
SELECT
    o.data_consegna,
    r.prodotto_id,
    q.configurazione,
    q.pezzi_per_collo,
    SUM(r.quantita_pezzi)                       AS fabbisogno_pezzi,
    CEIL(SUM(r.quantita_pezzi)::numeric
         / q.pezzi_per_collo)::int              AS colli_da_produrre,
    CEIL(SUM(r.quantita_pezzi)::numeric
         / q.pezzi_per_collo)::int
      * q.pezzi_per_collo                       AS lotto_suggerito_pezzi,
    CEIL(SUM(r.quantita_pezzi)::numeric
         / q.pezzi_per_collo)::int
      * q.pezzi_per_collo
      - SUM(r.quantita_pezzi)                   AS eccedenza_pezzi
FROM ordine o
JOIN ordine_riga r                ON r.ordine_id = o.id
JOIN vw_quanto_imballo_prodotto q ON q.prodotto_id = r.prodotto_id
GROUP BY o.data_consegna, r.prodotto_id, q.configurazione, q.pezzi_per_collo;
```

Esempio di output verificato (V7): con fabbisogno di 300 pezzi il lotto suggerito è 360 (5 colli, eccedenza 60); con fabbisogno di 200 pezzi il lotto suggerito è 216 (3 colli pieni, eccedenza 16). La colonna `eccedenza_pezzi` quantifica il costo dell'arrotondamento e permette di decidere caso per caso se produrre in eccesso o accettare un collo incompleto.

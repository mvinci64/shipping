-- ============================================================
-- VISCOTTA — Anagrafica configurazioni standard di imballo
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Questo file NON ricrea prodotto/ordine/ordine_riga: referenzia le
-- tabelle REALI del Portal (viscotta.products, viscotta.orders,
-- viscotta.order_items — vedi viscotta-order-portal/scripts/sql/
-- 005_portal_init.sql). Chiavi prodotto/ordine sono UUID, non SERIAL.
--
-- Le nuove tabelle di questo file (imballo, prodotto_confezione) vivono
-- nello stesso schema `viscotta` e usano FK reali verso viscotta.products.
--
-- NOTA STORICA — cosa NON c'è più e perché: la prima versione (Appendice
-- A del documento di valutazione) prevedeva anche `configurazione_collo`
-- / `configurazione_collo_riga`, un modello a "ricetta fissa per
-- prodotto" (es. uno scatolone sempre 3xWP50 dello stesso prodotto). Il
-- censimento imballi del 26/08 ha stabilito che la cartonizzazione reale
-- è dinamica e MISTA: uno scatolone da 6 posti si riempie con WP50/WP40
-- di prodotti diversi, first-fit (vedi prototype/cartonize.py e
-- sql/bi/fase0_simulazione_configurazioni.sql Q6). Il modello a ricetta
-- fissa è quindi stato rimosso: avrebbe prodotto viste sempre vuote
-- (richiedono un prodotto_id singolo per riga, che nel caso misto non
-- esiste). La cartonizzazione vera resta nel codice (shipping-api);
-- qui restano solo i FATTI (imballo, confezioni) e il ponte verso
-- miniMRP (V6/V7), ricostruito senza dipendere dalla ricetta fissa.
-- ============================================================

-- ============================================================
-- 1. IMBALLO — anagrafica di tutti gli imballi (esterni e interni)
-- ============================================================
CREATE TABLE viscotta.imballo (
    id             SERIAL PRIMARY KEY,
    codice         VARCHAR(20)  NOT NULL UNIQUE,      -- es. 'VISCOTTA', 'WP50'
    descrizione    VARCHAR(200),
    tipo           VARCHAR(10)  NOT NULL CHECK (tipo IN ('ESTERNO','INTERNO')),
    tara_g         INTEGER      NOT NULL CHECK (tara_g >= 0),
    lunghezza_mm   INTEGER,
    larghezza_mm   INTEGER,
    altezza_mm     INTEGER,
    capacita_posti INTEGER,      -- solo ESTERNO: posti totali (es. 6 per lo scatolone VISCOTTA)
    posti_occupati INTEGER,      -- solo INTERNO: posti che occupa (WP50=2, WP40=1)
    attivo         BOOLEAN      NOT NULL DEFAULT TRUE,
    creato_il      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    aggiornato_il  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Chiave composta (id, tipo): permette alle tabelle figlie di vincolare
-- via FK anche il TIPO di imballo referenziato (pattern "FK qualificata").
ALTER TABLE viscotta.imballo ADD CONSTRAINT uq_imballo_id_tipo UNIQUE (id, tipo);

-- ============================================================
-- 2. PRODOTTO_CONFEZIONE — come un prodotto entra nel suo imballo interno
--    (es. 24 chips in una scatola WP50). prodotto_id → prodotto REALE
--    del Portal (viscotta.products.id, UUID). Ogni prodotto ha in
--    genere DUE righe (WP50 e WP40): sono i due "quanti naturali", non
--    un'alternativa esclusiva — cartonize.py sceglie quale usare riga
--    per riga in base al residuo da imballare.
-- ============================================================
CREATE TABLE viscotta.prodotto_confezione (
    id                    SERIAL PRIMARY KEY,
    prodotto_id           UUID NOT NULL REFERENCES viscotta.products(id),
    imballo_interno_id    INTEGER NOT NULL,
    tipo_imballo          VARCHAR(10) NOT NULL DEFAULT 'INTERNO'
                          CHECK (tipo_imballo = 'INTERNO'),
    pezzi_per_confezione  INTEGER NOT NULL CHECK (pezzi_per_confezione > 0),
    peso_netto_g          NUMERIC(8,1) NOT NULL CHECK (peso_netto_g > 0),
    peso_collo_noto_g     NUMERIC(8,1),   -- pesata ufficiale (censimento), se nota — altrimenti derivato
    valido_dal            DATE NOT NULL DEFAULT CURRENT_DATE,
    valido_al             DATE,
    -- la FK composta garantisce che l'imballo referenziato sia di tipo INTERNO
    FOREIGN KEY (imballo_interno_id, tipo_imballo)
        REFERENCES viscotta.imballo (id, tipo),
    UNIQUE (prodotto_id, imballo_interno_id, valido_dal)
);

-- ============================================================
-- VISTA — peso ufficiale della scatola interna piena
-- (pesata censita se disponibile, altrimenti derivata da tara+grammatura)
-- ============================================================
CREATE VIEW viscotta.vw_peso_confezione AS
SELECT
    p.sku                                       AS sku,
    ii.codice                                   AS imballo,
    pc.pezzi_per_confezione,
    ii.posti_occupati,
    COALESCE(pc.peso_collo_noto_g,
             ii.tara_g + pc.peso_netto_g)       AS peso_confezione_g,
    (pc.peso_collo_noto_g IS NULL)              AS peso_derivato   -- true = da verificare con pesata
FROM viscotta.prodotto_confezione pc
JOIN viscotta.products p ON p.id = pc.prodotto_id
JOIN viscotta.imballo ii ON ii.id = pc.imballo_interno_id
WHERE pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE;

-- ============================================================
-- VISTA — copertura anagrafica: prodotti attivi senza confezione censita
-- ============================================================
CREATE VIEW viscotta.vw_copertura_prodotti AS
SELECT
    p.id,
    p.sku,
    p.name,
    bool_or(ii.codice = 'WP50') AS ha_wp50,
    bool_or(ii.codice = 'WP40') AS ha_wp40
FROM viscotta.products p
LEFT JOIN viscotta.prodotto_confezione pc
       ON pc.prodotto_id = p.id
      AND (pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE)
LEFT JOIN viscotta.imballo ii ON ii.id = pc.imballo_interno_id
WHERE p.is_active
GROUP BY p.id, p.sku, p.name;

-- ============================================================
-- V6. QUANTO DI IMBALLO PER PRODOTTO — ponte formale verso miniMRP
--     (vedi valutazione-cartonizzazione.md §4). I "multipli naturali"
--     di ogni prodotto: pezzi per confezione WP50 e WP40 affiancati.
--     Non dipende da configurazione_collo: sono i fatti censiti.
-- ============================================================
CREATE VIEW viscotta.vw_quanto_imballo_prodotto AS
SELECT
    p.id                                                     AS prodotto_id,
    p.sku,
    MAX(pc.pezzi_per_confezione) FILTER (WHERE ii.codice = 'WP50') AS pezzi_wp50,
    MAX(pc.pezzi_per_confezione) FILTER (WHERE ii.codice = 'WP40') AS pezzi_wp40
FROM viscotta.products p
JOIN viscotta.prodotto_confezione pc ON pc.prodotto_id = p.id
JOIN viscotta.imballo ii             ON ii.id = pc.imballo_interno_id
WHERE pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE
GROUP BY p.id, p.sku;

-- ============================================================
-- V7. LOTTO SUGGERITO — fabbisogno per data di consegna, arrotondato
--     per eccesso al quanto WP40 (la confezione più piccola: è il
--     grado di arrotondamento minimo sotto cui non si può scendere,
--     l'ottimizzazione WP50 la fa poi cartonize.py in fase di imballo).
--     Solo prenotazioni future: ordini 'submitted' con consegna futura
--     (viscotta.orders.status enum: draft/submitted/processing/
--     confirmed/shipped/completed/cancelled).
-- ============================================================
CREATE VIEW viscotta.vw_lotto_suggerito AS
SELECT
    o.requested_delivery_date               AS data_consegna,
    oi.product_id                           AS prodotto_id,
    q.sku,
    q.pezzi_wp40,
    SUM(oi.quantity)                        AS fabbisogno_pezzi,
    CEIL(SUM(oi.quantity) / q.pezzi_wp40)::int AS confezioni_wp40_da_produrre,
    CEIL(SUM(oi.quantity) / q.pezzi_wp40)::int
      * q.pezzi_wp40                        AS lotto_suggerito_pezzi,
    CEIL(SUM(oi.quantity) / q.pezzi_wp40)::int
      * q.pezzi_wp40
      - SUM(oi.quantity)                    AS eccedenza_pezzi
FROM viscotta.orders o
JOIN viscotta.order_items oi         ON oi.order_id = o.id
JOIN viscotta.vw_quanto_imballo_prodotto q ON q.prodotto_id = oi.product_id
WHERE o.status = 'submitted'
  AND o.requested_delivery_date >= CURRENT_DATE
  AND q.pezzi_wp40 IS NOT NULL
GROUP BY o.requested_delivery_date, oi.product_id, q.sku, q.pezzi_wp40;

-- ============================================================
-- Smoke test — richiede seed reale (vedi sql/fase1_seed_censimento.sql)
-- e ordini 'submitted' con consegna futura già presenti nel Portal.
-- ============================================================
SELECT * FROM viscotta.vw_peso_confezione ORDER BY sku, imballo;
SELECT * FROM viscotta.vw_copertura_prodotti ORDER BY sku;
SELECT * FROM viscotta.vw_quanto_imballo_prodotto ORDER BY sku;
SELECT * FROM viscotta.vw_lotto_suggerito ORDER BY data_consegna;

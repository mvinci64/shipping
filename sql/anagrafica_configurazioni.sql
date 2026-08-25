-- ============================================================
-- VISCOTTA — Anagrafica configurazioni standard di imballo
-- Dialetto: PostgreSQL 16
-- ============================================================

-- Tabelle di appoggio minime (già esistenti nel DB dell'Order Portal;
-- riportate qui solo per rendere lo script eseguibile in test)
CREATE TABLE prodotto (
    id            SERIAL PRIMARY KEY,
    codice        VARCHAR(30) NOT NULL UNIQUE,
    descrizione   VARCHAR(200)
);

CREATE TABLE ordine (
    id             SERIAL PRIMARY KEY,
    numero         VARCHAR(20) NOT NULL UNIQUE,
    cliente_id     INTEGER,
    data_consegna  DATE NOT NULL,
    stato          VARCHAR(20) NOT NULL DEFAULT 'ACCETTATO'
);

CREATE TABLE ordine_riga (
    id              SERIAL PRIMARY KEY,
    ordine_id       INTEGER NOT NULL REFERENCES ordine(id),
    prodotto_id     INTEGER NOT NULL REFERENCES prodotto(id),
    quantita_pezzi  INTEGER NOT NULL CHECK (quantita_pezzi > 0)
);

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

-- ============================================================
-- 2. PRODOTTO_CONFEZIONE — come un prodotto entra nel suo imballo interno
--    (es. 24 chips in una scatola WP50)
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
    -- la FK composta garantisce che l'imballo referenziato sia di tipo INTERNO
    FOREIGN KEY (imballo_interno_id, tipo_imballo)
        REFERENCES imballo (id, tipo),
    UNIQUE (prodotto_id, imballo_interno_id, valido_dal)
);

-- ============================================================
-- 3. CONFIGURAZIONE_COLLO — lo "scatolone" standard
--    (es. VISCOTTA-3xWP50: scatolone VISCOTTA con 3 WP50, ~6,1 kg)
-- ============================================================
CREATE TABLE configurazione_collo (
    id                     SERIAL PRIMARY KEY,
    codice                 VARCHAR(30) NOT NULL UNIQUE,   -- es. 'VISCOTTA-3xWP50'
    descrizione            VARCHAR(200),
    imballo_esterno_id     INTEGER NOT NULL,
    tipo_imballo           VARCHAR(10) NOT NULL DEFAULT 'ESTERNO'
                           CHECK (tipo_imballo = 'ESTERNO'),
    peso_lordo_nominale_g  INTEGER,                        -- es. 6100
    tolleranza_peso_pct    NUMERIC(4,1) NOT NULL DEFAULT 5.0,
    priorita               INTEGER NOT NULL DEFAULT 100,   -- preferenza in cartonizzazione (min = preferita)
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
    numero_confezioni   INTEGER NOT NULL CHECK (numero_confezioni > 0),  -- es. 3
    -- NULL = configurazione generica: qualunque prodotto confezionato
    -- in questo imballo interno; valorizzato = configurazione dedicata
    prodotto_id         INTEGER REFERENCES prodotto(id),
    FOREIGN KEY (imballo_interno_id, tipo_imballo)
        REFERENCES imballo (id, tipo),
    UNIQUE NULLS NOT DISTINCT (configurazione_id, imballo_interno_id, prodotto_id)
);

-- ============================================================
-- DATI DI ESEMPIO — il caso citato: scatolone VISCOTTA,
-- 3 scatole WP50 da 24 chips, ~6,1 kg lordi
-- ============================================================
INSERT INTO prodotto (codice, descrizione) VALUES
    ('CHIP-CLASSIC', 'Viscotta Chips Classiche');

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

-- Ordini di prova per le viste
INSERT INTO ordine (numero, cliente_id, data_consegna) VALUES
    ('ORD-2026-001', 1, DATE '2026-09-01'),
    ('ORD-2026-002', 2, DATE '2026-09-03');
INSERT INTO ordine_riga (ordine_id, prodotto_id, quantita_pezzi) VALUES
    (1, 1, 300),   -- 4 colli pieni + 12 residui
    (2, 1, 200);   -- 2 colli pieni + 56 pezzi residui

-- ============================================================
-- VISTE BI (Metabase) — di sola lettura
-- ============================================================

-- V1. Configurazione "esplosa": pezzi totali e peso lordo teorico per collo
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
JOIN imballo ie                 ON ie.id = cc.imballo_esterno_id
JOIN configurazione_collo_riga r ON r.configurazione_id = cc.id
JOIN imballo ii                 ON ii.id = r.imballo_interno_id
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

-- V3. Cartonizzazione prevista per riga d'ordine
--     (colli pieni, pezzi residui, % in colli pieni)
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
JOIN ordine_riga r              ON r.ordine_id = o.id
JOIN prodotto p                 ON p.id = r.prodotto_id
JOIN vw_configurazione_prodotto cp ON cp.prodotto_id = r.prodotto_id;

-- V4. Saturazione mensile per configurazione (KPI per dimensionare lo standard)
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
JOIN ordine o                   ON o.id = r.ordine_id
JOIN vw_configurazione_prodotto cp ON cp.prodotto_id = r.prodotto_id
GROUP BY cp.configurazione, date_trunc('month', o.data_consegna);

-- V5. Copertura anagrafica: prodotti senza confezione o senza configurazione
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

-- V6. Quanto di imballo per prodotto (vincolo per il miniMRP)
--     I "multipli naturali" di ogni prodotto: pezzi per confezione
--     e pezzi per collo pieno. È l'input con cui il piano di
--     produzione arrotonda i lotti giornalieri.
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
--     per eccesso a colli pieni. L'eccedenza è il "costo" della
--     ottimizzazione a valle, da confrontare con il costo dei
--     colli incompleti.
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

-- ============================================================
-- Smoke test
-- ============================================================
SELECT * FROM vw_configurazione_espansa;
SELECT * FROM vw_configurazione_prodotto;
SELECT * FROM vw_cartonizzazione_prevista ORDER BY numero_ordine;
SELECT * FROM vw_saturazione_configurazioni;
SELECT * FROM vw_copertura_prodotti;
SELECT * FROM vw_quanto_imballo_prodotto;
SELECT * FROM vw_lotto_suggerito ORDER BY data_consegna;

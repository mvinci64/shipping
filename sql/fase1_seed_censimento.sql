-- ============================================================
-- VISCOTTA — Fase 1: evoluzione DDL + seed dal censimento 26/08
-- Da eseguire DOPO anagrafica_configurazioni.sql (stesso DB).
-- Dialetto: PostgreSQL 16
-- ============================================================
-- Novità emerse dal censimento rispetto al modello iniziale:
--   1. Lo scatolone non ha una composizione fissa ma una CAPACITÀ:
--      6 "posti" (1 WP50 = 2 posti, 1 WP40 = 1 posto), riempiti
--      dinamicamente. Aggiungiamo capacita_posti / posti_occupati.
--   2. Ogni prodotto ha DUE formati di confezione (WP50 e WP40):
--      prodotto_confezione lo gestisce già (una riga per formato).
--   3. Peso collo pieno: dove noto dal censimento va registrato
--      come misura ufficiale (peso_collo_noto_g), perché non
--      sempre coincide con tara + pezzi × grammatura.
-- ============================================================

-- ---- 1. Estensione DDL: capacità a posti --------------------
ALTER TABLE imballo ADD COLUMN IF NOT EXISTS capacita_posti  INTEGER;  -- solo ESTERNO
ALTER TABLE imballo ADD COLUMN IF NOT EXISTS posti_occupati  INTEGER;  -- solo INTERNO

ALTER TABLE prodotto_confezione
    ADD COLUMN IF NOT EXISTS peso_collo_noto_g NUMERIC(8,1);  -- pesata ufficiale (censimento)

-- ---- 2. Imballi reali ---------------------------------------
INSERT INTO imballo (codice, descrizione, tipo, tara_g, capacita_posti, posti_occupati) VALUES
    ('VISCOTTA', 'Scatolone siglato VISCOTTA (6 posti WP40)', 'ESTERNO', 400, 6, NULL),  -- tara 400 g DA PESARE
    ('WP50',     'Scatola interna WP50',                      'INTERNO', 200, NULL, 2),
    ('WP40',     'Scatola interna WP40',                      'INTERNO', 150, NULL, 1)
ON CONFLICT (codice) DO UPDATE
    SET tara_g = EXCLUDED.tara_g,
        capacita_posti = EXCLUDED.capacita_posti,
        posti_occupati = EXCLUDED.posti_occupati;

-- ---- 3. Prodotti del censimento (se non già presenti) -------
-- Nel DB del Portal esistono già (products.sku): qui allineiamo
-- l'anagrafica di test. Adattare al momento del deploy reale.
INSERT INTO prodotto (codice, descrizione) VALUES
    ('CHMS50',    'Chips di Mandorla Salate 50 g'),
    ('GRM100',    'Grissini di Mandorla 100 g'),
    ('CANTS100',  'Cantucci Salati 100 g'),
    ('CMEN080',   'Chips Mandorla e Nocciola 80 g'),
    ('MCIOC080',  'Mandorle al Cioccolato 80 g'),
    ('MSAL080',   'Mandorle Salate 80 g'),
    ('TCAP075',   'Tortina Caprese 75 g'),
    ('CANT200',   'Cantucci Classici 200 g'),
    ('BRUT150',   'Brutti ma Buoni 150 g'),
    ('VPBUST08',  'Viscotta in Busta 80 g'),
    ('BOXOV',     'Box Ovale'),
    ('SCAT08V20', 'Scatola 08 V20')
ON CONFLICT (codice) DO NOTHING;

-- ---- 4. Confezionamenti censiti -----------------------------
-- Una riga per (prodotto, formato). peso_netto_g derivato dalla
-- grammatura SKU (DA VERIFICARE con pesata reale); dove il
-- censimento ha dato il peso del collo pieno, peso_collo_noto_g.
WITH dati (codice, imballo, pezzi, peso_netto_g, peso_collo_noto_g) AS (
    VALUES
        -- prodotti standard: 24 in WP50, 12 in WP40
        ('CHMS50',    'WP50', 24, 1200.0, NULL::numeric),
        ('CHMS50',    'WP40', 12,  600.0, NULL),
        ('GRM100',    'WP50', 24, 2400.0, NULL),
        ('GRM100',    'WP40', 12, 1200.0, NULL),
        ('CANTS100',  'WP50', 24, 2400.0, NULL),
        ('CANTS100',  'WP40', 12, 1200.0, NULL),
        ('CMEN080',   'WP50', 24, 1920.0, NULL),
        ('CMEN080',   'WP40', 12,  960.0, NULL),
        ('MCIOC080',  'WP50', 24, 1920.0, NULL),
        ('MCIOC080',  'WP40', 12,  960.0, NULL),
        ('MSAL080',   'WP50', 24, 1920.0, NULL),
        ('MSAL080',   'WP40', 12,  960.0, NULL),
        -- tortine capresi: 12 in WP50, 6 in WP40
        ('TCAP075',   'WP50', 12,  900.0, NULL),
        ('TCAP075',   'WP40',  6,  450.0, NULL),
        -- pesi collo noti dal censimento
        ('CANT200',   'WP50', 12, 2400.0, 2850.0),
        ('CANT200',   'WP40',  6, 1200.0, 1500.0),
        ('BRUT150',   'WP50', 12, 1800.0, 2250.0),
        ('BRUT150',   'WP40',  6,  900.0, 1200.0),
        ('VPBUST08',  'WP50', 12,  960.0, 2250.0),
        ('VPBUST08',  'WP40',  6,  480.0, 1200.0),
        -- solo WP40 (220 g/pezzo, collo pieno 1.450 g)
        ('BOXOV',     'WP40',  6, 1320.0, 1450.0),
        ('SCAT08V20', 'WP40',  6, 1320.0, 1450.0)
        -- scatole regalo/Natale: 6 per WP40, conf.5 paste 1.100 g,
        -- conf.10 paste 1.650 g — inserire con gli SKU definitivi
)
INSERT INTO prodotto_confezione
    (prodotto_id, imballo_interno_id, pezzi_per_confezione, peso_netto_g, peso_collo_noto_g)
SELECT p.id, i.id, d.pezzi, d.peso_netto_g, d.peso_collo_noto_g
FROM dati d
JOIN prodotto p ON p.codice = d.codice
JOIN imballo i  ON i.codice = d.imballo
ON CONFLICT (prodotto_id, imballo_interno_id, valido_dal) DO UPDATE
    SET pezzi_per_confezione = EXCLUDED.pezzi_per_confezione,
        peso_netto_g = EXCLUDED.peso_netto_g,
        peso_collo_noto_g = EXCLUDED.peso_collo_noto_g;

-- ---- 5. Vista: peso ufficiale della scatola piena -----------
-- peso_collo_noto_g (pesata) se disponibile, altrimenti derivato.
CREATE OR REPLACE VIEW vw_peso_confezione AS
SELECT
    p.codice                                   AS sku,
    i.codice                                   AS imballo,
    pc.pezzi_per_confezione,
    i.posti_occupati,
    COALESCE(pc.peso_collo_noto_g,
             i.tara_g + pc.peso_netto_g)       AS peso_confezione_g,
    (pc.peso_collo_noto_g IS NULL)             AS peso_derivato   -- true = da verificare con pesata
FROM prodotto_confezione pc
JOIN prodotto p ON p.id = pc.prodotto_id
JOIN imballo i  ON i.id = pc.imballo_interno_id
WHERE pc.valido_al IS NULL OR pc.valido_al >= CURRENT_DATE;

-- Smoke test
SELECT * FROM vw_peso_confezione ORDER BY sku, imballo;

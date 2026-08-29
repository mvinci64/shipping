-- ============================================================
-- VISCOTTA — Fase 1: seed anagrafica dal censimento imballi (26/08)
-- Da eseguire DOPO anagrafica_configurazioni.sql (stesso DB, schema viscotta).
-- Dialetto: PostgreSQL 16
--
-- Non tocca viscotta.products (catalogo del Portal, sola lettura da
-- qui): i prodotti vengono AGGANCIATI per sku, mai creati. Uno sku del
-- censimento senza corrispondenza in viscotta.products viene saltato
-- (segnalato nello smoke test finale), non inventato.
-- ============================================================

-- ---- 1. Imballi reali ---------------------------------------
INSERT INTO viscotta.imballo (codice, descrizione, tipo, tara_g, capacita_posti, posti_occupati) VALUES
    ('VISCOTTA', 'Scatolone siglato VISCOTTA (6 posti WP40)', 'ESTERNO', 400, 6, NULL),  -- tara 400 g DA PESARE
    ('WP50',     'Scatola interna WP50',                      'INTERNO', 200, NULL, 2),
    ('WP40',     'Scatola interna WP40',                      'INTERNO', 150, NULL, 1)
ON CONFLICT (codice) DO UPDATE
    SET tara_g = EXCLUDED.tara_g,
        capacita_posti = EXCLUDED.capacita_posti,
        posti_occupati = EXCLUDED.posti_occupati;

-- ---- 2. Confezionamenti censiti, agganciati a viscotta.products per sku ----
-- Una riga per (prodotto, formato). peso_netto_g derivato dalla
-- grammatura SKU (DA VERIFICARE con pesata reale); dove il censimento
-- ha dato il peso del collo pieno, peso_collo_noto_g.
WITH dati (sku, imballo, pezzi, peso_netto_g, peso_collo_noto_g) AS (
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
        -- prodotti nuovi (28/08): stesso comportamento di MSAL080 a livello
        -- di pezzi/collo; peso netto da grammatura 150 g / 200 g dichiarata
        ('MPEL150',   'WP50', 24, 3600.0, NULL),
        ('MPEL150',   'WP40', 12, 1800.0, NULL),
        ('MSGU150',   'WP50', 24, 3600.0, NULL),
        ('MSGU150',   'WP40', 12, 1800.0, NULL),
        ('MPEL200',   'WP50', 24, 4800.0, NULL),
        ('MPEL200',   'WP40', 12, 2400.0, NULL),
        ('MSGU200',   'WP50', 24, 4800.0, NULL),
        ('MSGU200',   'WP40', 12, 2400.0, NULL),
        -- tortine capresi: 12 in WP50, 6 in WP40
        ('TCAP075',   'WP50', 12,  900.0, NULL),
        ('TCAP075',   'WP40',  6,  450.0, NULL),
        -- pesi collo noti dal censimento
        ('CANT200',   'WP50', 12, 2400.0, 2850.0),
        ('CANT200',   'WP40',  6, 1200.0, 1500.0),
        ('BRUT150',   'WP50', 12, 1800.0, 2250.0),
        ('BRUT150',   'WP40',  6,  900.0, 1200.0),
        ('VP08BUST',  'WP50', 12,  960.0, 2250.0),
        ('VP08BUST',  'WP40',  6,  480.0, 1200.0),
        -- solo WP40 (220 g/pezzo, collo pieno 1.450 g)
        ('BOXOV',     'WP40',  6, 1320.0, 1450.0),
        ('SCAT20V08', 'WP40',  6, 1320.0, 1450.0)
        -- scatole regalo/Natale: 6 per WP40, conf.5 paste 1.100 g,
        -- conf.10 paste 1.650 g — inserire con gli SKU definitivi
)
INSERT INTO viscotta.prodotto_confezione
    (prodotto_id, imballo_interno_id, pezzi_per_confezione, peso_netto_g, peso_collo_noto_g)
SELECT p.id, i.id, d.pezzi, d.peso_netto_g, d.peso_collo_noto_g
FROM dati d
JOIN viscotta.products p ON p.sku = d.sku
JOIN viscotta.imballo i  ON i.codice = d.imballo
ON CONFLICT (prodotto_id, imballo_interno_id, valido_dal) DO UPDATE
    SET pezzi_per_confezione = EXCLUDED.pezzi_per_confezione,
        peso_netto_g = EXCLUDED.peso_netto_g,
        peso_collo_noto_g = EXCLUDED.peso_collo_noto_g;

-- ============================================================
-- Smoke test
-- ============================================================

-- SKU del censimento senza corrispondenza in viscotta.products
-- (da creare nel catalogo Portal, o da correggere qui se il codice è cambiato)
WITH sku_censiti (sku) AS (
    VALUES ('CHMS50'), ('GRM100'), ('CANTS100'), ('CMEN080'), ('MCIOC080'),
           ('MSAL080'), ('MPEL150'), ('MSGU150'), ('MPEL200'), ('MSGU200'),
           ('TCAP075'), ('CANT200'), ('BRUT150'), ('VP08BUST'),
           ('BOXOV'), ('SCAT20V08')
)
SELECT sc.sku AS sku_senza_prodotto_portal
FROM sku_censiti sc
LEFT JOIN viscotta.products p ON p.sku = sc.sku
WHERE p.id IS NULL;

SELECT * FROM viscotta.vw_peso_confezione ORDER BY sku, imballo;

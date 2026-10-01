-- ============================================================
-- VISCOTTA — Colli misti: gruppi sfusi con scatolone forzato
-- Dialetto: PostgreSQL 16 — schema viscotta
--
-- Estende colli_misti_manuali (Sprint 5, 14/09/2026) per coprire un
-- secondo caso reale: un gruppo di pezzi SFUSI (niente scatola interna,
-- es. torte caprese TCAP500IR) che l'operatore ha verificato fisicamente
-- entrare in uno scatolone di spedizione specifico, anche quando
-- l'algoritmo automatico lo considera già "pieno" per posti (es. 3×WP50
-- = 6/6 posti) e quindi non ce li metterebbe mai da solo (vedi il fix
-- "sfusi in scatolone pieno" del 18/09/2026, piano-sprint punto 20 — qui
-- l'eccezione è dichiarata a mano dall'operatore, non dedotta).
--
-- formato ora NULLABLE: NULL = gruppo sfuso (nessuna scatola interna,
-- nessun posto occupato — stesso trattamento di cartonize.SFUSO_SKUS).
-- scatolone_indice: 1-based, quale scatolone del risultato automatico
-- deve ricevere questo gruppo — solo per i gruppi sfusi (formato NULL);
-- per i colli misti normali (WP40/WP50) resta NULL, nessun cambiamento
-- di comportamento.
--
-- Primo caso reale: ORD-20260924-6100 (01/10/2026), 6 TCAP500IR
-- distribuite 3+3 — 3 nello scatolone 1 (con i pacchi da 1kg WP50,
-- verificato fisicamente dal reparto), 3 lasciate alla cartonizzazione
-- automatica nello scatolone successivo.
-- ============================================================

ALTER TABLE viscotta.colli_misti_manuali ALTER COLUMN formato DROP NOT NULL;

ALTER TABLE viscotta.colli_misti_manuali DROP CONSTRAINT colli_misti_manuali_formato_check;
ALTER TABLE viscotta.colli_misti_manuali ADD CONSTRAINT colli_misti_manuali_formato_check
    CHECK (formato IS NULL OR formato IN ('WP50', 'WP40'));

ALTER TABLE viscotta.colli_misti_manuali ADD COLUMN scatolone_indice INTEGER
    CHECK (scatolone_indice IS NULL OR scatolone_indice > 0);

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.colli_misti_manuali (order_number, formato, contenuto, scatolone_indice)
VALUES ('SMOKE-TEST-DDL', NULL, '[{"sku": "TCAP500IR", "pezzi": 3}]'::jsonb, 1)
RETURNING id, order_number, formato, contenuto, scatolone_indice, creata_at;

DELETE FROM viscotta.colli_misti_manuali WHERE order_number = 'SMOKE-TEST-DDL';

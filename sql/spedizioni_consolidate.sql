-- ============================================================
-- VISCOTTA — Spedizioni consolidate: più ordini in una sola spedizione
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Perché: fino al 21/10/2026 valeva l'invariante "una spedizione per
-- ordine" (vedi spedizioni_fsm.sql e CLAUDE.md). Nella pratica il reparto
-- ha trovato il caso opposto: STREGATE TEA SHOP con due ordini distinti
-- (ORD-20260613-9021 + ORD-20261019-8334) con la stessa data di consegna
-- e lo stesso destinatario — un solo collo fisico, un solo ritiro, quindi
-- deve essere UNA SOLA spedizione DHL (due bozze separate significano due
-- etichette corriere, due costi, due ritiri).
--
-- Scelta di disegno (minimo rischio sulle righe esistenti):
-- `order_number` resta la colonna NOT NULL di sempre e fa da CAPOFILA
-- della spedizione — tutto ciò che già funziona (indici, FSM, tracking,
-- etichetta) continua a leggerla senza modifiche. Gli ordini AGGIUNTIVI
-- consolidati nella stessa spedizione vanno in `ordini_aggregati`, che
-- per tutte le righe preesistenti resta l'array vuoto di default: nessuna
-- migrazione dati, nessun cambio di comportamento retroattivo.
--
-- L'insieme completo degli ordini di una spedizione è quindi
-- [order_number] || ordini_aggregati (vedi db.ordini_di_spedizione).
--
-- Nessuna FK verso viscotta.orders: stessa scelta di disaccoppiamento di
-- spedizioni_fsm.sql — Shipping non modifica lo stato del Portal.
-- ============================================================

ALTER TABLE viscotta.spedizioni
    ADD COLUMN IF NOT EXISTS ordini_aggregati VARCHAR(50)[] NOT NULL DEFAULT '{}';

-- Il capofila non può comparire anche tra gli aggregati (sarebbe contato
-- due volte in pesi/contrassegno/gate colli).
ALTER TABLE viscotta.spedizioni
    DROP CONSTRAINT IF EXISTS spedizioni_capofila_non_in_aggregati;
ALTER TABLE viscotta.spedizioni
    ADD CONSTRAINT spedizioni_capofila_non_in_aggregati
    CHECK (NOT (order_number = ANY (ordini_aggregati)));

-- Serve a fetch_ultima_spedizione_per_ordine / fetch_elenco_spedizioni:
-- dato un ordine QUALSIASI (capofila o aggregato) trovare la sua
-- spedizione, altrimenti un ordine consolidato risulterebbe "non
-- iniziata" nell'elenco di reparto pur essendo già spedito.
CREATE INDEX IF NOT EXISTS idx_spedizioni_ordini_aggregati
    ON viscotta.spedizioni USING GIN (ordini_aggregati);

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.spedizioni
    (order_number, product_code, pesi_scatoloni_kg, prezzo_stimato_eur, ordini_aggregati)
VALUES
    ('SMOKE-TEST-CONSOLIDATA', 'N', ARRAY[3.2, 1.5]::NUMERIC(6,3)[], 31.40,
     ARRAY['SMOKE-TEST-SECONDO']::VARCHAR(50)[])
RETURNING id, order_number, ordini_aggregati, stato;

-- Ritrovabile sia dal capofila sia dall'ordine aggregato.
SELECT order_number, ordini_aggregati
FROM viscotta.spedizioni
WHERE 'SMOKE-TEST-SECONDO' = ANY (ordini_aggregati);

-- Il CHECK deve rifiutare il capofila duplicato tra gli aggregati:
-- la prossima istruzione DEVE fallire (atteso: violazione del vincolo
-- spedizioni_capofila_non_in_aggregati). Eseguirla a parte.
-- INSERT INTO viscotta.spedizioni
--     (order_number, product_code, pesi_scatoloni_kg, ordini_aggregati)
-- VALUES ('X', 'N', ARRAY[1]::NUMERIC(6,3)[], ARRAY['X']::VARCHAR(50)[]);

DELETE FROM viscotta.spedizioni WHERE order_number = 'SMOKE-TEST-CONSOLIDATA';

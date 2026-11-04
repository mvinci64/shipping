-- ============================================================
-- VISCOTTA — Colli misti: etichetta con un altro SKU (override)
-- Dialetto: PostgreSQL 16 — schema viscotta
--
-- Estende colli_misti_manuali per un terzo caso reale: il contenuto del
-- collo è fatto di paste sfuse (righe d'ordine), ma a destino il collo
-- va presentato come il PRODOTTO FINITO in cui quelle paste sono state
-- confezionate — una scatola da 9. L'etichetta deve riportare lo SKU
-- della scatola e il numero di scatole, non le paste che la compongono.
--
-- Primo caso reale IVY CAFE DI TONELLI SIMONE (ORD-20260610-2352,
-- 04/11/2026):
--   VP09 20 + VP10 16 = 36 paste  ->  etichetta "SCATM09SA" 4 pz
--                                     (Scatola da 9 "Le Spiritose" assortite)
--   VP08 36            = 36 paste  ->  etichetta "SCATM09AC" 4 pz
--                                     (Scatola da 9 paste assortite ricoperte)
--
-- Perché un override e non una correzione dell'ordine: le scatole da 9
-- sono SKU disattivati in catalogo e il cliente le ha ordinate come
-- paste sfuse, quindi è così che vanno fatturate. L'ordine resta la
-- verità commerciale; questo cambia solo cosa si stampa sul collo
-- (scelta dell'utente, 04/11/2026).
--
-- `contenuto` continua a registrare le paste REALI: è da lì che si
-- calcola il peso del collo (nessun peso indovinato), e resta la
-- tracciabilità di cosa c'è dentro. L'override agisce solo sulla resa
-- dell'etichetta (vedi labels.py).
--
-- Entrambe le colonne NULL = comportamento di sempre ("Collo misto" con
-- l'elenco dei componenti): nessuna riga preesistente cambia.
-- ============================================================

ALTER TABLE viscotta.colli_misti_manuali
    ADD COLUMN IF NOT EXISTS etichetta_sku VARCHAR(50),
    ADD COLUMN IF NOT EXISTS etichetta_pezzi INTEGER;

-- Si valorizzano insieme o nessuna delle due: uno SKU senza quantità (o
-- viceversa) produrrebbe un'etichetta incompleta sul collo.
ALTER TABLE viscotta.colli_misti_manuali
    DROP CONSTRAINT IF EXISTS colli_misti_etichetta_coerente;
ALTER TABLE viscotta.colli_misti_manuali
    ADD CONSTRAINT colli_misti_etichetta_coerente
    CHECK (
        (etichetta_sku IS NULL AND etichetta_pezzi IS NULL)
        OR (etichetta_sku IS NOT NULL AND etichetta_pezzi IS NOT NULL AND etichetta_pezzi > 0)
    );

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.colli_misti_manuali
    (order_number, formato, contenuto, etichetta_sku, etichetta_pezzi)
VALUES
    ('SMOKE-TEST-ETICHETTA', 'WP40',
     '[{"sku": "VP09", "pezzi": 20}, {"sku": "VP10", "pezzi": 16}]'::jsonb,
     'SCATM09SA', 4)
RETURNING id, order_number, contenuto, etichetta_sku, etichetta_pezzi;

-- Il CHECK deve rifiutare lo SKU senza quantità: la prossima istruzione
-- DEVE fallire. Eseguirla a parte per verificarlo.
-- UPDATE viscotta.colli_misti_manuali SET etichetta_pezzi = NULL
-- WHERE order_number = 'SMOKE-TEST-ETICHETTA';

DELETE FROM viscotta.colli_misti_manuali WHERE order_number = 'SMOKE-TEST-ETICHETTA';

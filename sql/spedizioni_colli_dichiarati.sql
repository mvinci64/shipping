-- ============================================================
-- VISCOTTA — Colli dichiarati a mano su una spedizione
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Perché: i colli che la cartonizzazione calcola seguono la regola
-- "scatolone = 6 posti". In reparto capita di impacchettare più fitto e
-- far stare in DUE scatoloni quello che per la regola ne richiede TRE —
-- caso reale STREGATE TEA SHOP 26/10/2026: 13 posti di colli interni
-- (11 di ORD-20260613-9021 + 2 di ORD-20261019-8334) chiusi in 2
-- scatoloni invece dei 3 teorici.
--
-- Perché serve rappresentarlo: il numero di colli dichiarati a DHL deve
-- corrispondere ai pacchi FISICI. DHL stampa un'etichetta per collo e le
-- scansiona al ritiro: dichiararne 3 e consegnarne 2 lascia un'etichetta
-- orfana e un pacco "mancante", oltre a falsare la fatturazione.
--
-- Il concetto non è nuovo: `colli_misti_manuali.scatolone_indice` esiste
-- già per i gruppi sfusi che "l'operatore ha verificato fisicamente che
-- ci stanno, anche se l'algoritmo li considererebbe pieni per posti"
-- (vedi colli_misti_manuali_sfuso_indice.sql). Questa colonna estende la
-- stessa idea all'intera spedizione, inclusi i casi consolidati dove i
-- colli arrivano da ordini diversi.
--
-- Forma: NULL = comportamento di sempre (pesi calcolati dalla
-- cartonizzazione). Valorizzata = elenco dei pacchi REALI, in ordine:
--   [{"peso_kg": 8.66,  "ordini": ["ORD-20260613-9021"]},
--    {"peso_kg": 13.45, "ordini": ["ORD-20260613-9021","ORD-20261019-8334"]}]
-- `ordini` serve ai riferimenti stampati sull'etichetta del singolo
-- collo: un pacco che contiene merce di due ordini li riporta entrambi.
-- ============================================================

ALTER TABLE viscotta.spedizioni
    ADD COLUMN IF NOT EXISTS colli_dichiarati JSONB;

-- Se valorizzata deve essere un array non vuoto: una spedizione senza
-- pacchi non esiste, e un oggetto/stringa qui romperebbe il calcolo pesi.
ALTER TABLE viscotta.spedizioni
    DROP CONSTRAINT IF EXISTS spedizioni_colli_dichiarati_array;
ALTER TABLE viscotta.spedizioni
    ADD CONSTRAINT spedizioni_colli_dichiarati_array
    CHECK (
        colli_dichiarati IS NULL
        OR (jsonb_typeof(colli_dichiarati) = 'array' AND jsonb_array_length(colli_dichiarati) > 0)
    );

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.spedizioni
    (order_number, product_code, pesi_scatoloni_kg, ordini_aggregati, colli_dichiarati)
VALUES
    ('SMOKE-TEST-DICHIARATI', 'N', ARRAY[8.66, 13.45]::NUMERIC(6,3)[],
     ARRAY['SMOKE-TEST-SECONDO']::VARCHAR(50)[],
     '[{"peso_kg": 8.66, "ordini": ["SMOKE-TEST-DICHIARATI"]},
       {"peso_kg": 13.45, "ordini": ["SMOKE-TEST-DICHIARATI","SMOKE-TEST-SECONDO"]}]'::jsonb)
RETURNING id, order_number, colli_dichiarati;

-- Il CHECK deve rifiutare un array vuoto: la prossima istruzione DEVE
-- fallire. Eseguirla a parte per verificarlo.
-- UPDATE viscotta.spedizioni SET colli_dichiarati = '[]'::jsonb
-- WHERE order_number = 'SMOKE-TEST-DICHIARATI';

DELETE FROM viscotta.spedizioni WHERE order_number = 'SMOKE-TEST-DICHIARATI';

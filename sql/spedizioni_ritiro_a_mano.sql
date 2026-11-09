-- ============================================================
-- Ritiro a mano: merce che esce dalla sede senza corriere
-- (09/11/2026)
--
-- Caso reale UNIGROUP S.P.A. (ORD-20261104-3532 e ORD-20260928-3067):
-- il cliente passa a prendere la merce, non c'è nessuna spedizione DHL
-- da creare, nessuna etichetta corriere, nessun ritiro da prenotare. Fino
-- a oggi quegli ordini restavano per sempre "non iniziati" nell'elenco,
-- indistinguibili da quelli ancora da lavorare.
--
-- Scelta: NON un nuovo stato, ma un nuovo valore di `corriere`. Lo stato
-- 'ritirata' significa già "la merce ha lasciato la sede", che è
-- esattamente ciò che è accaduto; è il corriere a non esistere. Così
-- tutte le query che leggono gli stati continuano a valere senza
-- modifiche, e `corriere = 'ritiro_a_mano'` è il discriminante per i
-- campi che restano vuoti per forza (tracking, etichetta, conferma
-- ritiro DHL).
--
-- Da applicare PRIMA di deployare la versione di shipping-api che
-- contiene POST /spedizioni/ritiro-a-mano.
-- ============================================================

ALTER TABLE viscotta.spedizioni
    DROP CONSTRAINT spedizioni_corriere_check;

ALTER TABLE viscotta.spedizioni
    ADD CONSTRAINT spedizioni_corriere_check
    CHECK (corriere IN ('dhl', 'brt', 'ritiro_a_mano'));

-- Un ritiro a mano non ha tracking né conferma ritiro del corriere: i
-- campi DHL devono restare vuoti, altrimenti qualcuno li leggerebbe come
-- se una spedizione reale fosse stata emessa.
ALTER TABLE viscotta.spedizioni
    ADD CONSTRAINT spedizioni_ritiro_a_mano_senza_corriere
    CHECK (
        corriere <> 'ritiro_a_mano'
        OR (shipment_tracking_number IS NULL
            AND tracking_url IS NULL
            AND etichetta_pdf IS NULL
            AND dispatch_confirmation_number IS NULL
            AND product_code IS NULL
            AND prezzo_stimato_eur IS NULL)
    );

-- Verifica: il vincolo deve rifiutare un ritiro a mano con tracking.
-- Attesa: ERROR  violates check constraint "spedizioni_ritiro_a_mano_senza_corriere"
--
-- INSERT INTO viscotta.spedizioni
--     (order_number, corriere, stato, pesi_scatoloni_kg, shipment_tracking_number)
-- VALUES ('TEST-RITIRO', 'ritiro_a_mano', 'ritirata', ARRAY[1.000], '1234567890');

-- ============================================================
-- VISCOTTA — Spedizioni: FSM bozza → confermata → ritirata (Sprint 2)
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Stato del dominio Shipping, non del Portal: order_number è tenuto come
-- testo libero (nessuna FK verso viscotta.orders), coerente con la regola
-- "Shipping dipende dal Portal per anagrafica ordini, non lo modifica" —
-- disaccoppiato anche a livello di schema, non solo di scrittura.
--
-- Perché una FSM esplicita: MyDHL API non ha un vero draft nativo (a
-- differenza di BRT) — /rates quota senza creare nulla, /shipments crea
-- la spedizione reale con effetto (costo) immediato. La bozza qui è la
-- nostra, non quella di DHL: l'operatore deve SEMPRE controllare e
-- confermare esplicitamente prima che scatti una chiamata con effetto
-- reale (crea_spedizione / richiedi_pickup in app/dhl.py).
-- ============================================================

CREATE TABLE viscotta.spedizioni (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number                VARCHAR(50) NOT NULL,
    corriere                    VARCHAR(20) NOT NULL DEFAULT 'dhl' CHECK (corriere IN ('dhl', 'brt')),
    stato                       VARCHAR(20) NOT NULL DEFAULT 'bozza'
                                    CHECK (stato IN ('bozza', 'confermata', 'ritirata', 'fallita')),

    -- popolati alla creazione della bozza (POST /spedizioni), da
    -- cartonizzazione + dhl.valida_spedizione
    product_code                VARCHAR(10),
    pesi_scatoloni_kg           NUMERIC(6,3)[] NOT NULL,
    prezzo_stimato_eur          NUMERIC(10,2),

    -- popolati alla conferma (POST /spedizioni/{id}/conferma → dhl.crea_spedizione)
    shipment_tracking_number    VARCHAR(50),
    tracking_url                TEXT,
    etichetta_pdf                BYTEA,

    -- popolati al ritiro (POST /spedizioni/{id}/pickup → dhl.richiedi_pickup)
    dispatch_confirmation_number VARCHAR(50),

    -- solo se stato = 'fallita': dettaglio dell'errore DHL, bozza resta
    -- consultabile ma non riprovabile automaticamente (Sprint 5)
    errore                      TEXT,

    creata_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    confermata_at                TIMESTAMPTZ,
    ritirata_at                  TIMESTAMPTZ
);

CREATE INDEX idx_spedizioni_order_number ON viscotta.spedizioni (order_number);
CREATE INDEX idx_spedizioni_stato ON viscotta.spedizioni (stato);

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.spedizioni (order_number, product_code, pesi_scatoloni_kg, prezzo_stimato_eur)
VALUES ('SMOKE-TEST-DDL', 'N', ARRAY[3.2]::NUMERIC(6,3)[], 25.87)
RETURNING id, order_number, stato, creata_at;

DELETE FROM viscotta.spedizioni WHERE order_number = 'SMOKE-TEST-DDL';

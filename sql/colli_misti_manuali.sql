-- ============================================================
-- VISCOTTA — Colli misti manuali (Sprint 5)
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Un "collo misto" è una scatola interna (WP40/WP50) con PIÙ SKU insieme,
-- decisa a mano dal reparto quando i prodotti coinvolti non sono censiti
-- singolarmente in shipping-api/app/cartonize.py (es. VP01+VP06 in un
-- unico WP40 — primo caso reale: ORD-20260505-4944, 14/09/2026). La
-- cartonizzazione automatica continuerebbe a segnalarli come "non
-- censiti"; questa tabella permette di sottrarre le quantità già
-- assegnate manualmente e generare comunque l'etichetta collo corretta.
--
-- contenuto: [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]
-- — ogni sku deve avere un peso noto in GRAMMATURA_G (cartonize.py),
-- altrimenti il calcolo del peso fallisce esplicitamente (niente peso
-- indovinato per una spedizione DHL reale).
--
-- Nessuna FK verso viscotta.orders: stessa scelta di disaccoppiamento
-- di viscotta.spedizioni/colli_confermati — Shipping non modifica lo
-- stato del Portal.
-- ============================================================

CREATE TABLE viscotta.colli_misti_manuali (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(50) NOT NULL,
    formato      VARCHAR(10) NOT NULL CHECK (formato IN ('WP50', 'WP40')),
    contenuto    JSONB NOT NULL,
    creata_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_colli_misti_manuali_order_number ON viscotta.colli_misti_manuali (order_number);

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.colli_misti_manuali (order_number, formato, contenuto)
VALUES ('SMOKE-TEST-DDL', 'WP40', '[{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}]'::jsonb)
RETURNING id, order_number, formato, contenuto, creata_at;

DELETE FROM viscotta.colli_misti_manuali WHERE order_number = 'SMOKE-TEST-DDL';

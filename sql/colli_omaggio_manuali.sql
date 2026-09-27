-- ============================================================
-- VISCOTTA — Colli omaggio/promozione manuali (Sprint 5)
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Un "collo omaggio" è un WP40 aggiunto a mano dal reparto, non
-- corrispondente a una riga d'ordine (materiale POP, assaggi, cartello
-- vetrina, prodotti extra da campionatura...) — stesso spirito di
-- colli_misti_manuali (Sprint 5, 14/09/2026) ma senza SKU/pezzi: solo una
-- nota testuale libera che finisce stampata sull'etichetta collo insieme
-- alle altre (vedi labels.make_inner_labels_pdf, parametro note_omaggio).
--
-- Primo caso reale (27/09/2026): IMPORT-DMLAB-20260924-01 (materiale POP),
-- ORD-20260626-8577 (assaggi + cartello vetrina), ORD-20260723-7341
-- (30 paste di mandorla assortite flowpaccate, comprese quelle ricoperte
-- al cioccolato fondente).
--
-- Nessuna FK verso viscotta.orders: stessa scelta di disaccoppiamento
-- di viscotta.spedizioni/colli_confermati/colli_misti_manuali.
-- ============================================================

CREATE TABLE viscotta.colli_omaggio_manuali (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(50) NOT NULL,
    nota         TEXT NOT NULL,
    creata_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_colli_omaggio_manuali_order_number ON viscotta.colli_omaggio_manuali (order_number);

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.colli_omaggio_manuali (order_number, nota)
VALUES ('SMOKE-TEST-DDL', 'materiale POP')
RETURNING id, order_number, nota, creata_at;

DELETE FROM viscotta.colli_omaggio_manuali WHERE order_number = 'SMOKE-TEST-DDL';

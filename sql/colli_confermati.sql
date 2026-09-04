-- ============================================================
-- VISCOTTA — Conferma collo a fine linea (Sprint 3, coda)
-- Dialetto: PostgreSQL 16 — schema viscotta (stesso DB del Portal)
--
-- Un collo = uno scatolone della cartonizzazione (stesso indice leggibile
-- sull'etichetta scatolone come "Collo NN/totale" — vedi
-- labels.make_carton_summary_labels_pdf; l'etichetta non ha un barcode,
-- tolto il 04/09/2026 perché confondeva in reparto). Il reparto conferma
-- da shipping-web o digitando il codice a mano, a fine linea, per
-- confermare che quel collo è stato fisicamente chiuso e pronto: prima di
-- questa conferma, la spedizione non andrebbe confermata (POST
-- /spedizioni/{id}/conferma ha effetto reale, costo e ritiro reali).
--
-- Nessuna FK verso viscotta.orders/spedizioni: order_number testo libero,
-- stessa scelta di disaccoppiamento di viscotta.spedizioni (vedi
-- sql/spedizioni_fsm.sql) — Shipping non modifica lo stato del Portal.
-- n_totale non è vincolato qui: la cartonizzazione è ricalcolata al volo
-- dall'API a ogni conferma, così un indice fuori range viene rifiutato
-- dall'applicazione (422) invece che da un CHECK statico che potrebbe
-- disallinearsi se la cartonizzazione cambia (es. anagrafica configurazioni
-- aggiornata dopo la stampa delle etichette).
-- ============================================================

CREATE TABLE viscotta.colli_confermati (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number   VARCHAR(50) NOT NULL,
    indice_collo   SMALLINT NOT NULL CHECK (indice_collo > 0),
    confermato_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (order_number, indice_collo)
);

CREATE INDEX idx_colli_confermati_order_number ON viscotta.colli_confermati (order_number);

-- ============================================================
-- Smoke test
-- ============================================================
INSERT INTO viscotta.colli_confermati (order_number, indice_collo)
VALUES ('SMOKE-TEST-DDL', 1)
RETURNING id, order_number, indice_collo, confermato_at;

-- Il vincolo UNIQUE deve rifiutare una doppia conferma dello stesso collo:
-- decommentare per verificare a mano (fallisce con violazione UNIQUE, atteso)
-- INSERT INTO viscotta.colli_confermati (order_number, indice_collo) VALUES ('SMOKE-TEST-DDL', 1);

DELETE FROM viscotta.colli_confermati WHERE order_number = 'SMOKE-TEST-DDL';

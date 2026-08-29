-- ============================================================
-- VISCOTTA — Fase 0 (quick win read-only per viscotta-bi)
-- Simulazione configurazioni di imballo sugli ordini storici
-- ============================================================
-- Caratteristiche:
--   · SOLO SELECT: nessuna tabella nuova, nessun DDL, zero rischio.
--   · Le configurazioni CANDIDATE vivono in una CTE (VALUES):
--     si modificano direttamente nella query Metabase, anche in
--     riunione, e i numeri si aggiornano al volo.
--   · Ogni query (Q1..Q4) è autonoma: in Metabase diventa una
--     "domanda" (question) a sé, da comporre in una dashboard.
-- Schema BI reale (verificato):
--   viscotta.products     (id, sku, name, pack_size, is_active, ...)
--   viscotta.orders       (id, order_number, status, requested_delivery_date, ...)
--   viscotta.order_items  (id, order_id, product_id, quantity, ...)
-- Nota: quantity è trattata come numerica (FLOOR/MOD espliciti),
-- così le query funzionano anche se la colonna non è INTEGER.
-- Candidate e anagrafica confezioni: censimento riunione 26/08.
-- Regola fisica: scatolone VISCOTTA = 3 WP50 oppure 6 WP40
-- (1 WP50 = 2 posti WP40). Tare: WP50 200 g, WP40 150 g.
-- ============================================================


-- ------------------------------------------------------------
-- Q1. SATURAZIONE STORICA PER CONFIGURAZIONE CANDIDATA
--     "Se avessimo spedito con questo scatolone, quanto sarebbe
--      stato pieno?" — il KPI con cui si sceglie lo standard.
-- ------------------------------------------------------------
WITH config_candidate (config, sku, pezzi_per_confezione, confezioni_per_collo) AS (
    VALUES
        -- censimento riunione 26/08 (packaging: Vincenza + squadra)
        ('VISCOTTA-3xWP50-C',      'CHMS50',   24, 3),
        ('VISCOTTA-3xWP50-G',      'GRM100',   24, 3),
        ('VISCOTTA-3xWP50-CS',     'CANTS100', 24, 3),
        ('VISCOTTA-3xWP50-TCAP75', 'TCAP075',  12, 3),
        ('VISCOTTA-3xWP50-MSAL',   'MSAL080',  24, 3),
        ('VISCOTTA-3xWP50-MCIOC',  'MCIOC080', 24, 3),
        ('VISCOTTA-3xWP50-MCIOC',  'CMEN080',  24, 3),
        ('VISCOTTA-6xWP40-C',      'CHMS50',   12, 6),
        ('VISCOTTA-6xWP40-G',      'GRM100',   12, 6),
        ('VISCOTTA-6xWP40-CS',     'CANTS100', 12, 6),
        ('VISCOTTA-6xWP40-TCAP75', 'TCAP075',   6, 6),
        ('VISCOTTA-6xWP40-MSAL',   'MSAL080',  12, 6),
        ('VISCOTTA-6xWP40-MCIOC',  'MCIOC080', 12, 6),
        ('VISCOTTA-6xWP40-MCIOC',  'CMEN080',  12, 6)
),
candidate AS (
    SELECT *, pezzi_per_confezione * confezioni_per_collo AS pezzi_per_collo
    FROM config_candidate
)
SELECT
    c.config,
    c.sku,
    c.pezzi_per_collo,
    COUNT(DISTINCT o.id)                                   AS ordini,
    SUM(r.quantity)                                        AS pezzi_ordinati,
    SUM(FLOOR(r.quantity / c.pezzi_per_collo))::int        AS colli_pieni,
    SUM(MOD(r.quantity::numeric, c.pezzi_per_collo))       AS pezzi_fuori_collo,
    ROUND(100.0 * SUM(FLOOR(r.quantity / c.pezzi_per_collo) * c.pezzi_per_collo)
                / NULLIF(SUM(r.quantity), 0), 1)           AS saturazione_pct
FROM candidate c
JOIN viscotta.products p     ON p.sku = c.sku
JOIN viscotta.order_items r  ON r.product_id = p.id
JOIN viscotta.orders o       ON o.id = r.order_id
WHERE o.status NOT IN ('draft', 'cancelled')   -- adattare agli stati reali
--  AND o.requested_delivery_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY c.config, c.sku, c.pezzi_per_collo
ORDER BY saturazione_pct DESC;


-- ------------------------------------------------------------
-- Q2. QUANTI NATURALI DELLA DOMANDA
--     Le quantità più ordinate per prodotto: se i clienti
--     chiedono quasi sempre 72, 144, 216... il quanto è 72.
--     pack_size è la confezione attuale a catalogo: il confronto
--     con le quantità reali dice subito se è quella giusta.
-- ------------------------------------------------------------
SELECT
    p.sku,
    p.name,
    p.pack_size,
    r.quantity                       AS quantita_ordinata,
    COUNT(*)                         AS n_righe_ordine,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY p.sku), 1)
                                     AS pct_righe
FROM viscotta.order_items r
JOIN viscotta.products p ON p.id = r.product_id
JOIN viscotta.orders o   ON o.id = r.order_id
WHERE o.status NOT IN ('draft', 'cancelled')   -- adattare agli stati reali
--  AND o.requested_delivery_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY p.sku, p.name, p.pack_size, r.quantity
ORDER BY p.sku, n_righe_ordine DESC;


-- ------------------------------------------------------------
-- Q3. COMPATIBILITÀ ESATTA PER CANDIDATA
--     Percentuale di righe d'ordine perfettamente divisibili
--     per il collo candidato (zero residui senza arrotondare).
-- ------------------------------------------------------------
WITH config_candidate (config, sku, pezzi_per_confezione, confezioni_per_collo) AS (
    VALUES
        -- censimento riunione 26/08 (packaging: Vincenza + squadra)
        ('VISCOTTA-3xWP50-C',      'CHMS50',   24, 3),
        ('VISCOTTA-3xWP50-G',      'GRM100',   24, 3),
        ('VISCOTTA-3xWP50-CS',     'CANTS100', 24, 3),
        ('VISCOTTA-3xWP50-TCAP75', 'TCAP075',  12, 3),
        ('VISCOTTA-3xWP50-MSAL',   'MSAL080',  24, 3),
        ('VISCOTTA-3xWP50-MCIOC',  'MCIOC080', 24, 3),
        ('VISCOTTA-3xWP50-MCIOC',  'CMEN080',  24, 3),
        ('VISCOTTA-6xWP40-C',      'CHMS50',   12, 6),
        ('VISCOTTA-6xWP40-G',      'GRM100',   12, 6),
        ('VISCOTTA-6xWP40-CS',     'CANTS100', 12, 6),
        ('VISCOTTA-6xWP40-TCAP75', 'TCAP075',   6, 6),
        ('VISCOTTA-6xWP40-MSAL',   'MSAL080',  12, 6),
        ('VISCOTTA-6xWP40-MCIOC',  'MCIOC080', 12, 6),
        ('VISCOTTA-6xWP40-MCIOC',  'CMEN080',  12, 6)
),
candidate AS (
    SELECT *, pezzi_per_confezione * confezioni_per_collo AS pezzi_per_collo
    FROM config_candidate
)
SELECT
    c.config,
    c.sku,
    c.pezzi_per_collo,
    COUNT(*)                                                          AS righe_ordine,
    COUNT(*) FILTER (WHERE MOD(r.quantity::numeric, c.pezzi_per_collo) = 0)
                                                                      AS righe_esatte,
    ROUND(100.0 * COUNT(*) FILTER (WHERE MOD(r.quantity::numeric, c.pezzi_per_collo) = 0)
                / COUNT(*), 1)                                        AS pct_righe_esatte
FROM candidate c
JOIN viscotta.products p     ON p.sku = c.sku
JOIN viscotta.order_items r  ON r.product_id = p.id
JOIN viscotta.orders o       ON o.id = r.order_id
WHERE o.status NOT IN ('draft', 'cancelled')   -- adattare agli stati reali
GROUP BY c.config, c.sku, c.pezzi_per_collo
ORDER BY pct_righe_esatte DESC;


-- ------------------------------------------------------------
-- Q4. LOTTO SUGGERITO SIMULATO (anteprima delle viste V6/V7)
--     Fabbisogno per data di consegna arrotondato per eccesso
--     a colli pieni: quanti pezzi in più chiederebbe al
--     laboratorio la produzione "a scatoloni interi".
--     (Da confrontare, in Fase 1, con lotto_minimo/lotto_ottimale
--      già presenti in viscotta.prodotti del miniMRP.)
-- ------------------------------------------------------------
WITH config_candidate (config, sku, pezzi_per_confezione, confezioni_per_collo) AS (
    VALUES
        -- una candidata per prodotto: la preferita (WP50 pieni)
        ('VISCOTTA-3xWP50-C',      'CHMS50',   24, 3),
        ('VISCOTTA-3xWP50-G',      'GRM100',   24, 3),
        ('VISCOTTA-3xWP50-CS',     'CANTS100', 24, 3),
        ('VISCOTTA-3xWP50-TCAP75', 'TCAP075',  12, 3),
        ('VISCOTTA-3xWP50-MSAL',   'MSAL080',  24, 3),
        ('VISCOTTA-3xWP50-MCIOC',  'MCIOC080', 24, 3),
        ('VISCOTTA-3xWP50-MCIOC',  'CMEN080',  24, 3)
),
candidate AS (
    SELECT *, pezzi_per_confezione * confezioni_per_collo AS pezzi_per_collo
    FROM config_candidate
)
SELECT
    o.requested_delivery_date                              AS data_consegna,
    c.sku,
    c.config,
    SUM(r.quantity)                                        AS fabbisogno_pezzi,
    CEIL(SUM(r.quantity)::numeric / c.pezzi_per_collo)::int
                                                           AS colli_da_produrre,
    CEIL(SUM(r.quantity)::numeric / c.pezzi_per_collo)::int
      * c.pezzi_per_collo                                  AS lotto_suggerito_pezzi,
    CEIL(SUM(r.quantity)::numeric / c.pezzi_per_collo)::int
      * c.pezzi_per_collo - SUM(r.quantity)                AS eccedenza_pezzi
FROM candidate c
JOIN viscotta.products p     ON p.sku = c.sku
JOIN viscotta.order_items r  ON r.product_id = p.id
JOIN viscotta.orders o       ON o.id = r.order_id
WHERE o.status NOT IN ('draft', 'cancelled')   -- adattare agli stati reali
--  AND o.requested_delivery_date >= CURRENT_DATE - INTERVAL '3 months'
GROUP BY o.requested_delivery_date, c.sku, c.config, c.pezzi_per_collo
ORDER BY o.requested_delivery_date, c.sku;


-- ------------------------------------------------------------
-- Q5. COLLI MISTI (per il censimento "scatolone per scatolone")
--     Se dal censimento emergono scatoloni con PIÙ prodotti,
--     la configurazione diventa un GRUPPO di righe: una per
--     componente, con i pezzi di quel prodotto nel collo.
--     Un ordine riempie un collo misto solo se contiene TUTTI
--     i componenti nelle giuste proporzioni: i colli pieni per
--     ordine sono il MINIMO tra i componenti.
-- ------------------------------------------------------------
WITH candidate_riga (config, sku, pezzi_nel_collo) AS (
    VALUES
        -- censimento riunione 26/08: colli misti ricordati dalla squadra
        ('MISTO-CHIPS-GRISSINI1', 'CHMS50',    24),
        ('MISTO-CHIPS-GRISSINI1', 'CANTS100',  24),
        ('MISTO-CHIPS-GRISSINI1', 'GRM100',    24),
        ('MISTO-APERITIVI-TORTE', 'CHMS50',    24),
        ('MISTO-APERITIVI-TORTE', 'GRM100',    24),
        ('MISTO-APERITIVI-TORTE', 'TCAP075',   12),
        ('MISTO-CONF-TORTE',      'TCAP200SC',  6),
        ('MISTO-CONF-TORTE',      'SCATR05A',   3)
),
qta_ordine_prodotto AS (
    -- quantità totale per ordine e prodotto (somma le righe doppie)
    SELECT o.id AS order_id, p.sku, SUM(r.quantity) AS qta
    FROM viscotta.orders o
    JOIN viscotta.order_items r ON r.order_id = o.id
    JOIN viscotta.products p    ON p.id = r.product_id
    WHERE o.status NOT IN ('draft', 'cancelled')   -- adattare agli stati reali
--      AND o.requested_delivery_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY o.id, p.sku
),
per_ordine AS (
    -- per ogni ordine e configurazione mista: colli pieni = minimo
    -- tra i componenti (un componente assente = 0 colli)
    SELECT
        q.order_id,
        cr.config,
        MIN(FLOOR(COALESCE(qop.qta, 0) / cr.pezzi_nel_collo))::int AS colli_misti_pieni
    FROM (SELECT DISTINCT order_id FROM qta_ordine_prodotto) q
    CROSS JOIN (SELECT DISTINCT config FROM candidate_riga) c
    JOIN candidate_riga cr ON cr.config = c.config
    LEFT JOIN qta_ordine_prodotto qop
           ON qop.order_id = q.order_id AND qop.sku = cr.sku
    GROUP BY q.order_id, cr.config
)
SELECT
    config,
    COUNT(*)                                        AS ordini_analizzati,
    COUNT(*) FILTER (WHERE colli_misti_pieni > 0)   AS ordini_compatibili,
    ROUND(100.0 * COUNT(*) FILTER (WHERE colli_misti_pieni > 0)
                / COUNT(*), 1)                      AS pct_ordini_compatibili,
    SUM(colli_misti_pieni)                          AS colli_misti_totali
FROM per_ordine
GROUP BY config
ORDER BY pct_ordini_compatibili DESC;

-- ------------------------------------------------------------
-- Q6. CARTONIZZAZIONE ATTESA DEGLI ORDINI IN PRENOTAZIONE
--     Per ogni ordine: WP50/WP40 ottimizzati (prima WP50 pieni,
--     il resto in WP40), scatoloni attesi e posti liberi
--     nell'ultimo scatolone, dove vanno i prodotti non censiti.
--     Modello fisico: scatolone = 6 "posti WP40"; 1 WP50 = 2 posti.
-- ------------------------------------------------------------
WITH confezioni (sku, pz_wp50, pz_wp40, peso_wp50_kg, peso_wp40_kg) AS (
    VALUES
        -- censimento 26/08. Tare: WP50 200 g, WP40 150 g.
        ('CHMS50',    24,   12, NULL::numeric, NULL::numeric),
        ('GRM100',    24,   12, NULL, NULL),
        ('CANTS100',  24,   12, NULL, NULL),
        ('CMEN080',   24,   12, NULL, NULL),
        ('MCIOC080',  24,   12, NULL, NULL),
        ('MSAL080',   24,   12, NULL, NULL),
        ('MPEL150',   24,   12, NULL, NULL),
        ('MSGU150',   24,   12, NULL, NULL),
        ('MPEL200',   24,   12, NULL, NULL),
        ('MSGU200',   24,   12, NULL, NULL),
        ('TCAP075',   12,    6, NULL, NULL),
        ('CANT200',   12,    6, 2.85, 1.50),
        ('BRUT150',   12,    6, 2.25, 1.20),
        ('VP08BUST',  12,    6, 2.25, 1.20),
        ('BOXOV',   NULL,    6, NULL, 1.45),   -- 220 g/pezzo, solo WP40
        ('SCAT20V08', NULL,  6, NULL, 1.45)    -- 220 g/pezzo, solo WP40
        -- scatole regalo/Natale: 6 per WP40 (conf. 5 paste 1,10 kg;
        -- conf. 10 paste 1,65 kg) — aggiungere gli SKU esatti
),
righe AS (
    SELECT o.id AS order_id, o.order_number, o.requested_delivery_date,
           cu.company_name AS cliente,
           p.sku, SUM(r.quantity) AS qta
    FROM viscotta.orders o
    LEFT JOIN viscotta.customers cu ON cu.id = o.customer_id
    JOIN viscotta.order_items r ON r.order_id = o.id
    JOIN viscotta.products p    ON p.id = r.product_id
    WHERE o.status = 'submitted'
      AND o.crm_opportunity_id IS NOT NULL   -- "in prenotazione" = submitted E arrivato come Opportunity in CRM
    GROUP BY o.id, o.order_number, o.requested_delivery_date, cu.company_name, p.sku
),
calcolo AS (
    SELECT
        rg.*,
        (c.sku IS NULL) AS non_censito,
        CASE WHEN c.sku IS NULL OR c.pz_wp50 IS NULL THEN 0
             ELSE FLOOR(rg.qta / c.pz_wp50)::int END   AS n_wp50,
        CASE WHEN c.sku IS NULL THEN 0
             ELSE CEIL((rg.qta
                        - CASE WHEN c.pz_wp50 IS NULL THEN 0
                               ELSE FLOOR(rg.qta / c.pz_wp50) * c.pz_wp50 END
                       ) / c.pz_wp40::numeric)::int END AS n_wp40
    FROM righe rg
    LEFT JOIN confezioni c ON c.sku = rg.sku
)
SELECT
    order_number,
    cliente,
    requested_delivery_date                              AS data_consegna,
    SUM(n_wp50)                                          AS wp50,
    SUM(n_wp40)                                          AS wp40,
    CEIL((SUM(n_wp50) * 2 + SUM(n_wp40)) / 6.0)::int     AS scatoloni_attesi,
    (CEIL((SUM(n_wp50) * 2 + SUM(n_wp40)) / 6.0) * 6
       - (SUM(n_wp50) * 2 + SUM(n_wp40)))::int           AS posti_wp40_liberi,
    SUM(qta) FILTER (WHERE non_censito)                  AS pezzi_non_censiti,
    STRING_AGG(sku, ', ') FILTER (WHERE non_censito)     AS sku_non_censiti
FROM calcolo
GROUP BY order_number, cliente, requested_delivery_date
ORDER BY requested_delivery_date, order_number;

# Fase 0 — Simulazione configurazioni di imballo (viscotta-bi)

Kit **read-only** per Metabase: quattro query di sola lettura che simulano le configurazioni di scatolone candidate sugli ordini storici, **senza creare nulla** nel database. È il "quick win" della Fase 0: i numeri per decidere lo standard prima di scrivere una riga di codice applicativo.

## Come si usa in Metabase

1. **Nuova → Domanda → Query nativa** sul database della BI.
2. Incollare **una** delle query di `fase0_simulazione_configurazioni.sql` (Q1–Q4: una domanda Metabase per query).
3. Le configurazioni candidate sono nel blocco `VALUES` in testa alla query:

   ```sql
   VALUES
       ('VISCOTTA-3xWP50', 'CHIP-CLASSIC', 24, 3),
       ('VISCOTTA-4xWP50', 'CHIP-CLASSIC', 24, 4)
       -- (codice config, codice prodotto, pezzi per confezione, confezioni per collo)
   ```

   Si aggiungono/modificano righe direttamente lì — anche **in riunione, in diretta**: si salva e la dashboard si aggiorna. Nessuna tabella da creare, nessun permesso di scrittura.
4. Comporre le quattro domande in una dashboard "Fase 0 — Censimento imballi".

## Le quattro domande

| Query | Risponde a | Da guardare |
|---|---|---|
| **Q1** Saturazione storica | "Se avessimo spedito con questo scatolone, quanto sarebbe stato pieno?" | `saturazione_pct`: più alta = configurazione più adatta alla domanda reale |
| **Q2** Quanti naturali | "Che quantità ordinano davvero i clienti?" | Se le quantità ricorrenti sono multipli di un numero, quello è il quanto naturale |
| **Q3** Compatibilità esatta | "Quante righe d'ordine si spedirebbero senza residui, così come sono?" | `pct_righe_esatte` alta = pochi arrotondamenti necessari |
| **Q4** Lotto suggerito | "Quanto chiederebbe in più al laboratorio la produzione a scatoloni interi?" | `eccedenza_pezzi`: il costo dell'arrotondamento, giorno per giorno |
| **Q5** Colli misti | "Uno scatolone con più prodotti (es. 2 scatole chips + 1 torte) quanti ordini servirebbe?" | `pct_ordini_compatibili`: quanti ordini contengono tutti i componenti nelle giuste proporzioni |
| **Q6** Cartonizzazione attesa | "Per ogni ordine in prenotazione: quanti WP50, WP40 e scatoloni servono?" | `scatoloni_attesi`, `posti_wp40_liberi` (dove vanno i non censiti), `sku_non_censiti` da completare in anagrafica |

## Regole fisiche censite (riunione 26/08)

Scatolone VISCOTTA = **3 WP50 oppure 6 WP40** (1 WP50 = 2 posti WP40, combinabili). Tare: WP50 200 g, WP40 150 g. Ottimizzazione Q6: prima WP50 pieni, il resto in WP40; i prodotti non censiti riempiono i posti liberi dell'ultimo scatolone. L'anagrafica confezioni per SKU (pezzi per WP50/WP40 e pesi noti) è nella CTE `confezioni` in testa alla Q6: completare i pesi mancanti e gli SKU regalo/Natale.

## Come raccogliere i dati in riunione (due giri)

**Giro 1 — prodotto per prodotto**: per ogni prodotto, quale scatola interna, quanti pezzi, che peso, eccezioni. Alimenta Q1–Q4 (una riga `VALUES` per combinazione).

**Giro 2 — scatolone per scatolone**: per ogni scatolone assemblato in passato, cosa c'era dentro (quante scatole di quali prodotti) e con che frequenza. Se mono-prodotto → riga in Q1/Q3/Q4; se **misto** → gruppo di righe in Q5 (una per componente, stesso codice config). Domanda chiave da fare al banco: *"quando non riuscite a riempire uno scatolone, cosa fate?"* — le risposte sono le regole di cartonizzazione che il sistema dovrà replicare.

## Tabelle usate (schema BI reale)

Le query lavorano su `viscotta.products` (join per `sku`), `viscotta.orders` (data di consegna = `requested_delivery_date`) e `viscotta.order_items` (`quantity`, trattata come numerica). Due cose da rifinire al primo utilizzo: gli **stati ordine da escludere** nel filtro `o.status NOT IN ('draft','cancelled')` (adattare ai valori reali di `orders.status`) e gli **SKU** nei blocchi `VALUES`, da sostituire con quelli veri (`SELECT sku, name FROM viscotta.products WHERE is_active`). I filtri temporali sono predisposti come commento: scommentarli per limitare l'analisi agli ultimi N mesi.

Bonus dal catalogo: `products.pack_size` (mostrato in Q2) è la confezione attuale a catalogo, da confrontare con i quanti osservati; in `viscotta.prodotti` (miniMRP) esistono già `lotto_minimo` e `lotto_ottimale`, i naturali destinatari del lotto suggerito di Q4 in Fase 1.

## Nota per la riunione del censimento

Per ogni opzione di imballo censita servono quattro dati: **codice configurazione, prodotto, pezzi per confezione, confezioni per collo** (più tara e peso netto, che serviranno in Fase 1 per l'anagrafica vera — appendice A del documento di valutazione). Ogni opzione diventa una riga del blocco `VALUES` e Q1/Q3 dicono subito se regge la domanda storica.

---
*Query validate su PostgreSQL 16. Provenienza: `valutazione-cartonizzazione.md`, Appendice B (le viste V1–V7 sono la versione "a regime" di queste query, da attivare in Fase 1 quando esisterà l'anagrafica).*

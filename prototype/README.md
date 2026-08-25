# Prototipo cartonizzazione — pesi, etichette PDF, bozza DHL

Catena completa in un solo script, per gli scatoloni **composti automaticamente dal sistema**:

```
CSV ordini  →  cartonizzazione (WP50/WP40 → scatoloni)  →  pesi
            →  etichette PDF (100×150 mm, una per scatolone)
            →  bozza spedizione DHL (payload MyDHL API, un package per scatolone)
```

## Uso

```bash
python cartonize.py ordini_esempio.csv -o out/
```

Input: CSV con colonne `order_number, cliente, data_consegna, sku, qta` — è l'export della Q6 di Metabase o un estratto della lista prenotazioni. Output in `out/`: `cartonizzazione.json` (composizione e pesi), `etichette_<ordine>.pdf`, `dhl_draft_<ordine>.json`.

Richiede Python 3 + `reportlab` (`pip install reportlab`).

## Regole implementate (censimento 26/08)

Scatolone VISCOTTA = 6 posti (WP50 = 2, WP40 = 1), riempito first-fit con le WP50 prima. Per ogni riga d'ordine: WP50 piene, resto in WP40 (l'ultima può essere parziale, peso proporzionale). I prodotti non censiti compaiono sull'etichetta dell'ultimo scatolone come "da sistemare a mano". L'anagrafica confezioni è il dizionario `CONFEZIONI` in testa allo script — specchio 1:1 della tabella `prodotto_confezione` (Fase 1: lo script leggerà dal DB invece che dal dizionario).

## Cosa manca per andare in produzione

1. **Pesi**: quelli marcati `derivato` vanno verificati con la bilancia (grammatura SKU + tara); quelli `censimento` sono già pesate dichiarate. Manca la tara reale dello scatolone VISCOTTA (oggi 400 g stimati) e le dimensioni in cm per DHL.
2. **DHL**: il payload è pronto per il flusso di **validazione** MyDHL API (verifica dati senza emissione etichetta). Servono: credenziali API dal referente DHL Express, account number, indirizzo mittente e indirizzi cliente (da `viscotta.customers`). Alla conferma, lo stesso payload emette AWB ed etichetta DHL. In alternativa BRT ha il flusso draft nativo (create → confirm/delete).
3. **Lotto/scadenza in etichetta**: campo predisposto, si riempie in Fase 2 quando la stampa avviene a fine linea (dati dal miniMRP).
4. **SKU scatole regalo/Natale**: da aggiungere all'anagrafica appena confermati i codici.

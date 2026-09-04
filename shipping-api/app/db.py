"""Connessione PostgreSQL — stesso DB dell'Order Portal, schema `viscotta`."""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection() -> psycopg.Connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL non impostata (vedi .env.example)")
    return psycopg.connect(DATABASE_URL)


def ping() -> bool:
    """Usata da /health: True se il DB risponde, False altrimenti (non solleva)."""
    if not DATABASE_URL:
        return False
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


def fetch_order(order_number: str) -> dict | None:
    """Ordine reale (righe sku/qta + cliente) da viscotta.orders/order_items.
    None se l'ordine non esiste. order_items.sku è denormalizzato in tabella,
    non serve join a products."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT o.id, c.company_name, o.requested_delivery_date
            FROM viscotta.orders o
            JOIN viscotta.customers c ON c.id = o.customer_id
            WHERE o.order_number = %s
            """,
            (order_number,),
        ).fetchone()
        if row is None:
            return None
        order_id, cliente, data_consegna = row

        righe = conn.execute(
            "SELECT sku, quantity FROM viscotta.order_items WHERE order_id = %s",
            (order_id,),
        ).fetchall()

    return {
        "order_number": order_number,
        "cliente": cliente,
        "data_consegna": data_consegna.isoformat() if data_consegna else None,
        "righe": [{"sku": sku, "qta": float(qta)} for sku, qta in righe],
    }


def fetch_destinatario(order_number: str) -> dict | None:
    """Indirizzo + contatto del cliente per un ordine reale. None se
    l'ordine non esiste. shipping_address è testo libero (via + CAP in
    coda, es. "Via Rossi 1, 18035"); city/province/country sono colonne
    separate — parsing del CAP a carico del chiamante. email/telefono
    servono solo per dhl.crea_spedizione (non per /rates); se customers.phone
    è vuoto si fa fallback su easyfatt.tanagrafica (tel poi cell), agganciata
    via codanagr = customers.code — chiave pulita, senza duplicati su
    codanagr. Molti clienti restano comunque senza telefono in nessuna delle
    due fonti — vedi note in routers/spedizioni.py."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT c.company_name, c.shipping_address, c.city, c.province,
                   c.country, c.email,
                   COALESCE(NULLIF(c.phone, ''), a.tel, a.cell) AS telefono
            FROM viscotta.orders o
            JOIN viscotta.customers c ON c.id = o.customer_id
            LEFT JOIN easyfatt.tanagrafica a ON a.codanagr = c.code
            WHERE o.order_number = %s
            """,
            (order_number,),
        ).fetchone()
    if row is None:
        return None
    nome, indirizzo, citta, provincia, paese, email, telefono = row
    return {
        "nome": nome,
        "indirizzo": indirizzo,
        "citta": citta,
        "provincia": provincia,
        "paese": paese,
        "email": email,
        "telefono": telefono,
    }


def fetch_ultimo_lotto(sku: str) -> dict | None:
    """Ultimo lotto prodotto per uno SKU, da easyfatt.tmovmagazz (il gestionale,
    non miniMRP: viscotta.ordini_produzione non ha lotto/scadenza affidabili,
    solo order_number/note libere). Si produce fresco su ordine, quindi
    l'ultimo movimento di carico (qtacaricata) per l'articolo è il lotto
    dell'ordine corrente — niente FEFO su giacenza aggregata. None se lo SKU
    non esiste in easyfatt o non ha mai avuto un carico."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT m.lotto, m.datascadenza
            FROM easyfatt.tmovmagazz m
            JOIN easyfatt.tarticoli a ON a.idarticolo = m.idarticolo
            WHERE a.codarticolo = %s AND m.qtacaricata IS NOT NULL
            ORDER BY m.data DESC, m.numproduz DESC NULLS LAST
            LIMIT 1
            """,
            (sku,),
        ).fetchone()
    if row is None:
        return None
    lotto, scadenza = row
    return {"lotto": lotto, "scadenza": scadenza.isoformat() if scadenza else None}


def fetch_gtin(sku: str) -> str | None:
    """GTIN-13 (EAN-13) dell'articolo, da easyfatt.tarticoli.codbarre — non
    censito per tutti gli articoli (27 su 202 al 01/09/2026). None se lo SKU
    non esiste o non ha un codice a barre valorizzato."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT codbarre FROM easyfatt.tarticoli WHERE codarticolo = %s AND codbarre IS NOT NULL AND codbarre <> ''",
            (sku,),
        ).fetchone()
    return row[0] if row else None


def fetch_nome_prodotto(sku: str) -> str | None:
    """Nome leggibile del prodotto (viscotta.products.name), da mostrare
    accanto allo SKU sull'etichetta collo — a fine linea, di fretta, deve
    essere chiaro cosa contiene il collo senza dover ricordare a memoria
    ogni SKU. None se lo SKU non esiste in anagrafica prodotti."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT name FROM viscotta.products WHERE sku = %s",
            (sku,),
        ).fetchone()
    return row[0] if row else None


_COLONNE_SPEDIZIONE = """
    id, order_number, corriere, stato, product_code, pesi_scatoloni_kg,
    prezzo_stimato_eur, shipment_tracking_number, tracking_url,
    dispatch_confirmation_number, errore, creata_at, confermata_at, ritirata_at
"""


def _spedizione_da_riga(row) -> dict:
    (id_, order_number, corriere, stato, product_code, pesi_scatoloni_kg,
     prezzo_stimato_eur, shipment_tracking_number, tracking_url,
     dispatch_confirmation_number, errore, creata_at, confermata_at, ritirata_at) = row
    return {
        "id": str(id_),
        "order_number": order_number,
        "corriere": corriere,
        "stato": stato,
        "product_code": product_code,
        "pesi_scatoloni_kg": [float(p) for p in pesi_scatoloni_kg],
        "prezzo_stimato_eur": float(prezzo_stimato_eur) if prezzo_stimato_eur is not None else None,
        "shipment_tracking_number": shipment_tracking_number,
        "tracking_url": tracking_url,
        "dispatch_confirmation_number": dispatch_confirmation_number,
        "errore": errore,
        "creata_at": creata_at.isoformat(),
        "confermata_at": confermata_at.isoformat() if confermata_at else None,
        "ritirata_at": ritirata_at.isoformat() if ritirata_at else None,
    }


def crea_spedizione_bozza(
    *, order_number: str, corriere: str, product_code: str,
    pesi_scatoloni_kg: list[float], prezzo_stimato_eur: float | None,
) -> dict:
    """Crea la riga in stato 'bozza' — nessuna chiamata DHL con effetto
    reale è ancora avvenuta a questo punto (solo /rates, già fatto dal
    chiamante per ottenere product_code/prezzo)."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            INSERT INTO viscotta.spedizioni
                (order_number, corriere, product_code, pesi_scatoloni_kg, prezzo_stimato_eur)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING {_COLONNE_SPEDIZIONE}
            """,
            (order_number, corriere, product_code, pesi_scatoloni_kg, prezzo_stimato_eur),
        ).fetchone()
        conn.commit()
    return _spedizione_da_riga(row)


def fetch_spedizione(spedizione_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {_COLONNE_SPEDIZIONE} FROM viscotta.spedizioni WHERE id = %s",
            (spedizione_id,),
        ).fetchone()
    return _spedizione_da_riga(row) if row else None


def conferma_spedizione(
    spedizione_id: str, *, shipment_tracking_number: str, tracking_url: str, etichetta_pdf: bytes,
) -> dict:
    """bozza -> confermata. Chiamare SOLO dopo che dhl.crea_spedizione ha
    già avuto successo (ha effetto reale, non è idempotente)."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            UPDATE viscotta.spedizioni
            SET stato = 'confermata', shipment_tracking_number = %s,
                tracking_url = %s, etichetta_pdf = %s, confermata_at = now()
            WHERE id = %s AND stato = 'bozza'
            RETURNING {_COLONNE_SPEDIZIONE}
            """,
            (shipment_tracking_number, tracking_url, etichetta_pdf, spedizione_id),
        ).fetchone()
        conn.commit()
    if row is None:
        raise ValueError(f"Spedizione {spedizione_id} non trovata o non in stato 'bozza'")
    return _spedizione_da_riga(row)


def registra_pickup_spedizione(spedizione_id: str, *, dispatch_confirmation_number: str) -> dict:
    """confermata -> ritirata. Chiamare SOLO dopo che dhl.richiedi_pickup
    ha già avuto successo (ha effetto reale, non è idempotente)."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            UPDATE viscotta.spedizioni
            SET stato = 'ritirata', dispatch_confirmation_number = %s, ritirata_at = now()
            WHERE id = %s AND stato = 'confermata'
            RETURNING {_COLONNE_SPEDIZIONE}
            """,
            (dispatch_confirmation_number, spedizione_id),
        ).fetchone()
        conn.commit()
    if row is None:
        raise ValueError(f"Spedizione {spedizione_id} non trovata o non in stato 'confermata'")
    return _spedizione_da_riga(row)


def segna_spedizione_fallita(spedizione_id: str, *, errore: str) -> None:
    """La bozza resta consultabile (stato 'fallita', non cancellata) —
    l'operatore capisce cos'è andato storto senza dover rifare tutto da
    capo; nessun retry automatico (Sprint 5)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE viscotta.spedizioni SET stato = 'fallita', errore = %s WHERE id = %s",
            (errore, spedizione_id),
        )
        conn.commit()


def elimina_spedizione_bozza(spedizione_id: str) -> bool:
    """Cancella SOLO se ancora in stato 'bozza' (nessuna chiamata DHL con
    effetto reale è mai avvenuta per questa riga). True se cancellata."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM viscotta.spedizioni WHERE id = %s AND stato = 'bozza'",
            (spedizione_id,),
        )
        conn.commit()
        return cur.rowcount > 0


def conferma_collo(order_number: str, indice_collo: int) -> None:
    """Registra la scansione di fine linea per un collo (uno scatolone).
    Idempotente: se il collo era già confermato, non fa nulla (doppia
    scansione per errore non deve rompere il flusso a reparto)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO viscotta.colli_confermati (order_number, indice_collo)
            VALUES (%s, %s)
            ON CONFLICT (order_number, indice_collo) DO NOTHING
            """,
            (order_number, indice_collo),
        )
        conn.commit()


def annulla_conferma_collo(order_number: str, indice_collo: int) -> bool:
    """Annulla una conferma (errore di scansione). True se c'era da annullare."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM viscotta.colli_confermati WHERE order_number = %s AND indice_collo = %s",
            (order_number, indice_collo),
        )
        conn.commit()
        return cur.rowcount > 0


def fetch_colli_confermati(order_number: str) -> set[int]:
    with get_connection() as conn:
        righe = conn.execute(
            "SELECT indice_collo FROM viscotta.colli_confermati WHERE order_number = %s",
            (order_number,),
        ).fetchall()
    return {indice for (indice,) in righe}


def fetch_orders_by_delivery_date(data_consegna) -> list[dict]:
    """Tutti gli ordini realmente 'in prenotazione' con questa data di consegna
    richiesta — stesso filtro di vw_lotto_suggerito / Q6. "In prenotazione"
    richiede sia status='submitted' sia un riscontro reale in CRM
    (crm_opportunity_id valorizzato): esistono ordini submitted con
    crm_export_status='exported' ma senza crm_opportunity_id, cioè mai
    arrivati a diventare un'Opportunity in CRM — non vanno cartonizzati.
    Un dict per ordine, righe sku/qta incluse (stessa forma di fetch_order)."""
    with get_connection() as conn:
        ordini = conn.execute(
            """
            SELECT o.id, o.order_number, c.company_name
            FROM viscotta.orders o
            JOIN viscotta.customers c ON c.id = o.customer_id
            WHERE o.status = 'submitted'
              AND o.crm_opportunity_id IS NOT NULL
              AND o.requested_delivery_date = %s
            ORDER BY o.order_number
            """,
            (data_consegna,),
        ).fetchall()

        risultato = []
        for order_id, order_number, cliente in ordini:
            righe = conn.execute(
                "SELECT sku, quantity FROM viscotta.order_items WHERE order_id = %s",
                (order_id,),
            ).fetchall()
            risultato.append({
                "order_number": order_number,
                "cliente": cliente,
                "righe": [{"sku": sku, "qta": float(qta)} for sku, qta in righe],
            })
    return risultato


def fetch_orders_da_spedire(data_da, data_a) -> list[dict]:
    """Come fetch_orders_by_delivery_date, ma su un intervallo di date invece
    che un giorno singolo — per la vista d'insieme "ordini da spedire" del
    reparto (GET /spedizioni/elenco), non per la cartonizzazione di un
    singolo giorno. Stesso filtro "in prenotazione" (status='submitted' +
    crm_opportunity_id valorizzato). Ordinato per data consegna poi ordine."""
    with get_connection() as conn:
        ordini = conn.execute(
            """
            SELECT o.id, o.order_number, c.company_name, o.requested_delivery_date
            FROM viscotta.orders o
            JOIN viscotta.customers c ON c.id = o.customer_id
            WHERE o.status = 'submitted'
              AND o.crm_opportunity_id IS NOT NULL
              AND o.requested_delivery_date BETWEEN %s AND %s
            ORDER BY o.requested_delivery_date, o.order_number
            """,
            (data_da, data_a),
        ).fetchall()

        risultato = []
        for order_id, order_number, cliente, data_consegna in ordini:
            righe = conn.execute(
                "SELECT sku, quantity FROM viscotta.order_items WHERE order_id = %s",
                (order_id,),
            ).fetchall()
            risultato.append({
                "order_number": order_number,
                "cliente": cliente,
                "data_consegna": data_consegna.isoformat() if data_consegna else None,
                "righe": [{"sku": sku, "qta": float(qta)} for sku, qta in righe],
            })
    return risultato


def fetch_ultima_spedizione_per_ordine(order_number: str) -> dict | None:
    """Spedizione più recente per un ordine (per order_number possono
    esistere più righe nel tempo: una bozza cancellata e poi ricreata, un
    tentativo fallito seguito da uno riuscito). None se non è mai stata
    creata nessuna bozza — l'ordine è "da iniziare", non è un errore."""
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT {_COLONNE_SPEDIZIONE} FROM viscotta.spedizioni
            WHERE order_number = %s
            ORDER BY creata_at DESC
            LIMIT 1
            """,
            (order_number,),
        ).fetchone()
    return _spedizione_da_riga(row) if row else None

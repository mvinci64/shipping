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
            SELECT o.id, c.company_name
            FROM viscotta.orders o
            JOIN viscotta.customers c ON c.id = o.customer_id
            WHERE o.order_number = %s
            """,
            (order_number,),
        ).fetchone()
        if row is None:
            return None
        order_id, cliente = row

        righe = conn.execute(
            "SELECT sku, quantity FROM viscotta.order_items WHERE order_id = %s",
            (order_id,),
        ).fetchall()

    return {
        "order_number": order_number,
        "cliente": cliente,
        "righe": [{"sku": sku, "qta": float(qta)} for sku, qta in righe],
    }


def fetch_destinatario(order_number: str) -> dict | None:
    """Indirizzo di spedizione del cliente per un ordine reale. None se
    l'ordine non esiste. shipping_address è testo libero (via + CAP in
    coda, es. "Via Rossi 1, 18035"); city/province/country sono colonne
    separate — parsing del CAP a carico del chiamante."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT c.shipping_address, c.city, c.province, c.country
            FROM viscotta.orders o
            JOIN viscotta.customers c ON c.id = o.customer_id
            WHERE o.order_number = %s
            """,
            (order_number,),
        ).fetchone()
    if row is None:
        return None
    indirizzo, citta, provincia, paese = row
    return {
        "indirizzo": indirizzo,
        "citta": citta,
        "provincia": provincia,
        "paese": paese,
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

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

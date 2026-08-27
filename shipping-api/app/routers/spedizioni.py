import datetime
import re

from fastapi import APIRouter, HTTPException

from app import db, dhl
from app.cartonize import cartonize_order

router = APIRouter()

# customers.country nel DB del Portal è testo libero ("Italia"), MyDHL API
# vuole ISO2. Mappa minima: si estende quando arrivano ordini esteri reali.
PAESE_ISO2 = {"italia": "IT"}

CAP_RE = re.compile(r"(\d{5})\s*$")


def _estrai_cap(indirizzo: str) -> str:
    match = CAP_RE.search(indirizzo or "")
    if not match:
        raise HTTPException(
            status_code=422,
            detail=f"CAP non trovato in coda all'indirizzo: {indirizzo!r}",
        )
    return match.group(1)


def _iso2(paese: str) -> str:
    codice = PAESE_ISO2.get((paese or "").strip().lower())
    if codice is None:
        raise HTTPException(
            status_code=422,
            detail=f"Paese '{paese}' non mappato a un codice ISO2 (vedi PAESE_ISO2 in spedizioni.py)",
        )
    return codice


@router.post("/spedizioni/valida/{order_number}")
def valida_spedizione(order_number: str) -> dict:
    """Quota la spedizione di un ordine reale via MyDHL API (POST /rates) —
    nessuna spedizione viene creata, nessuna etichetta emessa: è la
    "bozza" emulata. Combina cartonizzazione (pesi scatoloni) e indirizzo
    cliente da DB."""
    ordine = db.fetch_order(order_number)
    if ordine is None:
        raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")

    destinatario = db.fetch_destinatario(order_number)
    cartonizzazione = cartonize_order(ordine["righe"])
    if cartonizzazione["n_scatoloni"] == 0:
        raise HTTPException(status_code=422, detail="Nessuno scatolone: ordine senza prodotti censiti")

    pesi_kg = [round(c["peso_g"] / 1000, 3) for c in cartonizzazione["scatoloni"]]

    try:
        risposta_dhl = dhl.valida_spedizione(
            destinatario_cap=_estrai_cap(destinatario["indirizzo"]),
            destinatario_citta=destinatario["citta"],
            destinatario_provincia=destinatario["provincia"] or "",
            destinatario_paese=_iso2(destinatario["paese"]),
            pesi_scatoloni_kg=pesi_kg,
            data_spedizione_iso=datetime.date.today().isoformat(),
        )
    except dhl.DHLConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except dhl.DHLAPIError as exc:
        raise HTTPException(status_code=502, detail={"dhl_status": exc.status_code, "dhl_payload": exc.payload}) from exc

    return {
        "order_number": order_number,
        "n_scatoloni": cartonizzazione["n_scatoloni"],
        "pesi_scatoloni_kg": pesi_kg,
        "dhl": risposta_dhl,
    }

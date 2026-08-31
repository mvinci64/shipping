import base64
import datetime
import re

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import db, dhl
from app.cartonize import cartonize_order

router = APIRouter()


class SpedizioneResponse(BaseModel):
    id: str
    order_number: str
    corriere: str
    stato: str
    product_code: str | None
    pesi_scatoloni_kg: list[float]
    prezzo_stimato_eur: float | None
    shipment_tracking_number: str | None
    tracking_url: str | None
    dispatch_confirmation_number: str | None
    errore: str | None
    creata_at: str
    confermata_at: str | None
    ritirata_at: str | None

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


def _ordine_e_destinatario(order_number: str) -> tuple[dict, dict]:
    ordine = db.fetch_order(order_number)
    if ordine is None:
        raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
    return ordine, db.fetch_destinatario(order_number)


def _pesi_scatoloni_kg(ordine: dict) -> list[float]:
    cartonizzazione = cartonize_order(ordine["righe"])
    if cartonizzazione["n_scatoloni"] == 0:
        raise HTTPException(status_code=422, detail="Nessuno scatolone: ordine senza prodotti censiti")
    return [round(c["peso_g"] / 1000, 3) for c in cartonizzazione["scatoloni"]]


def _quota(destinatario: dict, pesi_kg: list[float], data_iso: str) -> dict:
    try:
        return dhl.valida_spedizione(
            destinatario_cap=_estrai_cap(destinatario["indirizzo"]),
            destinatario_citta=destinatario["citta"],
            destinatario_provincia=destinatario["provincia"] or "",
            destinatario_paese=_iso2(destinatario["paese"]),
            pesi_scatoloni_kg=pesi_kg,
            data_spedizione_iso=data_iso,
        )
    except dhl.DHLConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except dhl.DHLAPIError as exc:
        raise HTTPException(status_code=502, detail={"dhl_status": exc.status_code, "dhl_payload": exc.payload}) from exc


def _scegli_prodotto(risposta_dhl: dict) -> tuple[str, float | None]:
    """EXPRESS DOMESTIC standard di default (il prodotto giusto per noi,
    vedi email Alessandro Menna 31/08); altrimenti il primo prodotto
    restituito. La risposta /rates può contenere prodotti non pertinenti
    (es. MEDICAL EXPRESS) — non va preso il primo alla cieca."""
    prodotti = risposta_dhl.get("products", [])
    if not prodotti:
        raise HTTPException(status_code=502, detail="MyDHL API non ha restituito nessun prodotto")
    scelto = next((p for p in prodotti if p["productName"] == "EXPRESS DOMESTIC"), prodotti[0])
    prezzo = next((pr["price"] for pr in scelto.get("totalPrice", []) if pr["currencyType"] == "BILLC"), None)
    return scelto["productCode"], prezzo


@router.post("/spedizioni/valida/{order_number}")
def valida_spedizione(order_number: str) -> dict:
    """Quota la spedizione di un ordine reale via MyDHL API (POST /rates) —
    nessuna spedizione viene creata, nessuna etichetta emessa: è la
    "bozza" emulata. Combina cartonizzazione (pesi scatoloni) e indirizzo
    cliente da DB."""
    ordine, destinatario = _ordine_e_destinatario(order_number)
    pesi_kg = _pesi_scatoloni_kg(ordine)
    risposta_dhl = _quota(destinatario, pesi_kg, datetime.date.today().isoformat())
    return {
        "order_number": order_number,
        "n_scatoloni": len(pesi_kg),
        "pesi_scatoloni_kg": pesi_kg,
        "dhl": risposta_dhl,
    }


@router.post("/spedizioni", response_model=SpedizioneResponse)
def crea_bozza_spedizione(order_number: str) -> SpedizioneResponse:
    """Crea la bozza (stato 'bozza'): quota via /rates e salva su DB.
    Nessuna chiamata DHL con effetto reale — solo /rates, come /valida."""
    ordine, destinatario = _ordine_e_destinatario(order_number)
    pesi_kg = _pesi_scatoloni_kg(ordine)
    risposta_dhl = _quota(destinatario, pesi_kg, datetime.date.today().isoformat())
    product_code, prezzo = _scegli_prodotto(risposta_dhl)
    bozza = db.crea_spedizione_bozza(
        order_number=order_number, corriere="dhl", product_code=product_code,
        pesi_scatoloni_kg=pesi_kg, prezzo_stimato_eur=prezzo,
    )
    return SpedizioneResponse(**bozza)


@router.get("/spedizioni/{spedizione_id}", response_model=SpedizioneResponse)
def dettaglio_spedizione(spedizione_id: str) -> SpedizioneResponse:
    spedizione = db.fetch_spedizione(spedizione_id)
    if spedizione is None:
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata")
    return SpedizioneResponse(**spedizione)


@router.post("/spedizioni/{spedizione_id}/conferma", response_model=SpedizioneResponse)
def conferma_spedizione(spedizione_id: str) -> SpedizioneResponse:
    """bozza -> confermata. QUESTA CHIAMATA HA EFFETTO REALE: crea la
    spedizione DHL vera con relativo costo (dhl.crea_spedizione). Va
    invocata solo dopo controllo umano della bozza (GET /spedizioni/{id})."""
    spedizione = db.fetch_spedizione(spedizione_id)
    if spedizione is None:
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata")
    if spedizione["stato"] != "bozza":
        raise HTTPException(status_code=409, detail=f"Spedizione in stato '{spedizione['stato']}', non 'bozza'")

    ordine, destinatario = _ordine_e_destinatario(spedizione["order_number"])
    try:
        risposta = dhl.crea_spedizione(
            order_number=spedizione["order_number"],
            product_code=spedizione["product_code"],
            destinatario_nome=destinatario["nome"] or ordine["cliente"],
            destinatario_email=destinatario["email"] or "",
            destinatario_telefono=destinatario["telefono"] or "",
            destinatario_indirizzo=destinatario["indirizzo"],
            destinatario_cap=_estrai_cap(destinatario["indirizzo"]),
            destinatario_citta=destinatario["citta"],
            destinatario_provincia=destinatario["provincia"] or "",
            destinatario_paese=_iso2(destinatario["paese"]),
            pesi_scatoloni_kg=spedizione["pesi_scatoloni_kg"],
            data_spedizione_iso=datetime.date.today().isoformat(),
        )
    except (dhl.DHLConfigError, dhl.DHLAPIError) as exc:
        db.segna_spedizione_fallita(spedizione_id, errore=str(exc))
        status = 502 if isinstance(exc, dhl.DHLAPIError) else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    etichetta_b64 = risposta["documents"][0]["content"]
    aggiornata = db.conferma_spedizione(
        spedizione_id,
        shipment_tracking_number=risposta["shipmentTrackingNumber"],
        tracking_url=risposta.get("trackingUrl", ""),
        etichetta_pdf=base64.b64decode(etichetta_b64),
    )
    return SpedizioneResponse(**aggiornata)


@router.get("/spedizioni/{spedizione_id}/etichetta")
def etichetta_spedizione(spedizione_id: str) -> Response:
    """PDF etichetta ufficiale DHL — solo per spedizioni 'confermata'/'ritirata'."""
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT etichetta_pdf, order_number FROM viscotta.spedizioni WHERE id = %s",
            (spedizione_id,),
        ).fetchone()
    if row is None or row[0] is None:
        raise HTTPException(status_code=404, detail="Etichetta non disponibile (spedizione non confermata?)")
    pdf, order_number = row
    return Response(
        content=bytes(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dhl_{order_number}.pdf"'},
    )


@router.post("/spedizioni/{spedizione_id}/pickup", response_model=SpedizioneResponse)
def richiedi_pickup_spedizione(spedizione_id: str, data_pickup: datetime.date | None = None) -> SpedizioneResponse:
    """confermata -> ritirata. QUESTA CHIAMATA HA EFFETTO REALE: prenota
    il ritiro DHL vero (dhl.richiedi_pickup). data_pickup di default
    domani (i ritiri lo stesso giorno spesso non sono più prenotabili
    dopo il cutoff — vedi pickupCapabilities in /rates)."""
    spedizione = db.fetch_spedizione(spedizione_id)
    if spedizione is None:
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata")
    if spedizione["stato"] != "confermata":
        raise HTTPException(status_code=409, detail=f"Spedizione in stato '{spedizione['stato']}', non 'confermata'")

    data_iso = (data_pickup or (datetime.date.today() + datetime.timedelta(days=1))).isoformat()
    try:
        risposta = dhl.richiedi_pickup(
            shipment_tracking_number=spedizione["shipment_tracking_number"],
            product_code=spedizione["product_code"],
            pesi_scatoloni_kg=spedizione["pesi_scatoloni_kg"],
            data_pickup_iso=data_iso,
        )
    except (dhl.DHLConfigError, dhl.DHLAPIError) as exc:
        status = 502 if isinstance(exc, dhl.DHLAPIError) else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    aggiornata = db.registra_pickup_spedizione(
        spedizione_id, dispatch_confirmation_number=risposta["dispatchConfirmationNumbers"][0],
    )
    return SpedizioneResponse(**aggiornata)


@router.delete("/spedizioni/{spedizione_id}", status_code=204)
def elimina_bozza_spedizione(spedizione_id: str) -> None:
    """Cancella SOLO se ancora in stato 'bozza' — nessuna chiamata DHL con
    effetto reale è mai avvenuta per una bozza, quindi non c'è nulla da
    annullare lato DHL."""
    if not db.elimina_spedizione_bozza(spedizione_id):
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata o non in stato 'bozza'")

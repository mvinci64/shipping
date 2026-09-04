import datetime
import re

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import db
from app.cartonize import cartonize_order
from app.day_plan import make_day_plan_pdf
from app.labels import make_carton_summary_labels_pdf, make_inner_labels_pdf

router = APIRouter()


class RigaOrdine(BaseModel):
    sku: str
    qta: float


class RichiestaCartonizzazione(BaseModel):
    order_number: str
    cliente: str = ""
    righe: list[RigaOrdine]


class ScatolaInterna(BaseModel):
    formato: str
    sku: str
    pezzi: int
    peso_g: int


class Scatolone(BaseModel):
    posti_usati: int
    contenuto: list[ScatolaInterna]
    peso_g: int


class SkuNonCensito(BaseModel):
    sku: str
    qta: float


class RisultatoCartonizzazione(BaseModel):
    order_number: str
    scatoloni: list[Scatolone]
    n_scatoloni: int
    posti_liberi_ultimo: int
    peso_totale_kg: float
    non_censiti: list[SkuNonCensito]


@router.post("/cartonizzazioni", response_model=RisultatoCartonizzazione)
def crea_cartonizzazione(richiesta: RichiestaCartonizzazione) -> RisultatoCartonizzazione:
    rows = [{"sku": r.sku, "qta": r.qta} for r in richiesta.righe]
    result = cartonize_order(rows)
    return RisultatoCartonizzazione(order_number=richiesta.order_number, **result)


@router.post("/cartonizzazioni/etichette-colli")
def etichette_colli(richiesta: RichiestaCartonizzazione) -> Response:
    """Etichette per ogni collo interno (WP50/WP40), lotto/quantità —
    quella che conta ai fini di tracciabilità. Distinta dall'etichetta
    scatolone (riepilogo) e dall'etichetta ufficiale del corriere."""
    rows = [{"sku": r.sku, "qta": r.qta} for r in richiesta.righe]
    result = cartonize_order(rows)
    pdf = make_inner_labels_pdf(richiesta.order_number, richiesta.cliente, result)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etichette_colli_{richiesta.order_number}.pdf"'},
    )


def _ordine_reale(order_number: str) -> dict:
    ordine = db.fetch_order(order_number)
    if ordine is None:
        raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
    return ordine


# Formato del codice di conferma: "<order_number>-NN", lo stesso testo
# "Collo NN/totale" leggibile sull'etichetta scatolone (vedi
# labels.make_carton_summary_labels_pdf) — NN a 2 cifre, indice 1-based.
# L'etichetta scatolone non ha più un barcode (tolto il 04/09/2026): la
# conferma è digitata a mano o fatta dalla UI shipping-web, non scansionata.
CODICE_COLLO_RE = re.compile(r"^(?P<order_number>.+)-(?P<indice>\d{2})$")


def _parse_codice_collo(codice: str) -> tuple[str, int]:
    match = CODICE_COLLO_RE.match(codice.strip())
    if not match:
        raise HTTPException(
            status_code=422,
            detail=f"Codice collo non riconosciuto: {codice!r} (atteso '<ordine>-NN', es. 'ORD-20260910-1234-01')",
        )
    return match.group("order_number"), int(match.group("indice"))


class ScansioneCollo(BaseModel):
    codice: str


class StatoColli(BaseModel):
    order_number: str
    n_totale: int
    confermati: list[int]
    mancanti: list[int]
    completo: bool


def _stato_colli(order_number: str) -> StatoColli:
    ordine = _ordine_reale(order_number)
    result = cartonize_order(ordine["righe"])
    n_totale = result["n_scatoloni"]
    confermati = sorted(db.fetch_colli_confermati(order_number))
    mancanti = sorted(set(range(1, n_totale + 1)) - set(confermati))
    return StatoColli(
        order_number=order_number, n_totale=n_totale, confermati=confermati,
        mancanti=mancanti, completo=n_totale > 0 and not mancanti,
    )


@router.get("/cartonizzazioni/{order_number}", response_model=RisultatoCartonizzazione)
def cartonizzazione_ordine_reale(order_number: str) -> RisultatoCartonizzazione:
    """Cartonizzazione di un ordine reale, letto da viscotta.orders/order_items."""
    ordine = _ordine_reale(order_number)
    result = cartonize_order(ordine["righe"])
    return RisultatoCartonizzazione(order_number=order_number, **result)


@router.get("/cartonizzazioni/{order_number}/etichette-colli")
def etichette_colli_ordine_reale(order_number: str, con_lotto: bool = True) -> Response:
    """Etichette collo (WP50/WP40) per un ordine reale, letto dal DB.
    Lotto/scadenza reali da easyfatt.tmovmagazz (ultimo carico per SKU);
    se uno SKU non ha mai avuto un carico in EasyFatt resta il placeholder.

    con_lotto=false: stampa in anticipo, quando solo alcuni SKU dell'ordine
    sono già stati prodotti (es. un ordine con più prodotti, di cui oggi è
    uscito dal laboratorio solo il primo) — lotto/scadenza verrebbero
    disallineati per il resto dell'ordine, quindi vengono omessi per tutta
    l'etichetta. Il barcode resta comunque (GTIN da solo, senza lotto):
    identifica il prodotto anche quando lotto/scadenza non sono ancora
    affidabili."""
    ordine = _ordine_reale(order_number)
    result = cartonize_order(ordine["righe"])
    skus = {item["sku"] for carton in result["scatoloni"] for item in carton["contenuto"]}
    nomi = {sku: nome for sku in skus if (nome := db.fetch_nome_prodotto(sku)) is not None}
    gtins = {sku: gtin for sku in skus if (gtin := db.fetch_gtin(sku)) is not None}
    lotti = {}
    if con_lotto:
        lotti = {sku: lotto for sku in skus if (lotto := db.fetch_ultimo_lotto(sku)) is not None}
    pdf = make_inner_labels_pdf(order_number, ordine["cliente"], result, lotti, gtins, nomi, mostra_lotto=con_lotto)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etichette_colli_{order_number}.pdf"'},
    )


@router.get("/cartonizzazioni/{order_number}/etichette-scatolone")
def etichette_scatolone_ordine_reale(order_number: str) -> Response:
    """Etichetta scatolone (una per collo di spedizione): riepilogo interno
    di cosa contiene, con dati reali dell'ordine (cliente, data consegna).
    Distinta dalle etichette collo WP50/WP40 e dall'etichetta ufficiale del
    corriere (DHL/BRT), che resta da applicare a parte alla conferma
    spedizione."""
    ordine = _ordine_reale(order_number)
    result = cartonize_order(ordine["righe"])
    pdf = make_carton_summary_labels_pdf(order_number, ordine["cliente"], ordine.get("data_consegna"), result)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etichette_scatolone_{order_number}.pdf"'},
    )


@router.post("/cartonizzazioni/colli/conferma", response_model=StatoColli)
def conferma_collo_scansionato(scansione: ScansioneCollo) -> StatoColli:
    """Conferma di fine linea: il codice "<ordine>-NN" leggibile
    sull'etichetta scatolone, digitato a mano (dalla UI shipping-web o via
    questo endpoint) — non c'è più un barcode da scansionare (tolto il
    04/09/2026, confondeva in reparto). Idempotente: confermare due volte
    lo stesso collo per errore non è un errore. 422 se l'indice non esiste
    nella cartonizzazione attuale dell'ordine (es. codice di un ordine
    sbagliato, o cartonizzazione cambiata dopo la stampa)."""
    order_number, indice = _parse_codice_collo(scansione.codice)
    stato = _stato_colli(order_number)
    if indice > stato.n_totale:
        raise HTTPException(
            status_code=422,
            detail=f"Collo {indice} non esiste per l'ordine {order_number} (cartonizzazione attuale: {stato.n_totale} colli)",
        )
    db.conferma_collo(order_number, indice)
    return _stato_colli(order_number)


@router.get("/cartonizzazioni/{order_number}/colli", response_model=StatoColli)
def stato_colli_ordine(order_number: str) -> StatoColli:
    """Stato delle conferme di fine linea per un ordine: quanti colli sono
    stati scansionati, quali mancano. Usare prima di confermare la
    spedizione (POST /spedizioni/{id}/conferma ha effetto reale)."""
    return _stato_colli(order_number)


@router.delete("/cartonizzazioni/{order_number}/colli/{indice_collo}", response_model=StatoColli)
def annulla_conferma_collo(order_number: str, indice_collo: int) -> StatoColli:
    """Annulla la conferma di un collo (errore di scansione)."""
    db.annulla_conferma_collo(order_number, indice_collo)
    return _stato_colli(order_number)


@router.get("/cartonizzazioni/piano-giorno/{data_consegna}")
def piano_giorno(data_consegna: datetime.date) -> Response:
    """Piano di cartonizzazione del giorno: un PDF A4, 4 ordini per pagina
    (2×2, linee di taglio), da stampare e allegare fisicamente a ogni ordine
    in laboratorio — documento ufficiale pre-produzione. Un ordine per
    ritaglio: le etichette collo WP50/WP40 (lotto/scadenza reali) arrivano
    dopo, a produzione fatta."""
    ordini = db.fetch_orders_by_delivery_date(data_consegna)
    if not ordini:
        raise HTTPException(
            status_code=404,
            detail=f"Nessun ordine 'submitted' con consegna {data_consegna.isoformat()}",
        )
    pdf = make_day_plan_pdf(data_consegna.isoformat(), ordini)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="piano_{data_consegna.isoformat()}.pdf"'},
    )

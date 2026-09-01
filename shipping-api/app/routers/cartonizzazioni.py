import datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import db
from app.cartonize import cartonize_order
from app.day_plan import make_day_plan_pdf
from app.labels import make_inner_labels_pdf

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


@router.get("/cartonizzazioni/{order_number}", response_model=RisultatoCartonizzazione)
def cartonizzazione_ordine_reale(order_number: str) -> RisultatoCartonizzazione:
    """Cartonizzazione di un ordine reale, letto da viscotta.orders/order_items."""
    ordine = _ordine_reale(order_number)
    result = cartonize_order(ordine["righe"])
    return RisultatoCartonizzazione(order_number=order_number, **result)


@router.get("/cartonizzazioni/{order_number}/etichette-colli")
def etichette_colli_ordine_reale(order_number: str) -> Response:
    """Etichette collo (WP50/WP40) per un ordine reale, letto dal DB.
    Lotto/scadenza reali da easyfatt.tmovmagazz (ultimo carico per SKU);
    se uno SKU non ha mai avuto un carico in EasyFatt resta il placeholder."""
    ordine = _ordine_reale(order_number)
    result = cartonize_order(ordine["righe"])
    skus = {item["sku"] for carton in result["scatoloni"] for item in carton["contenuto"]}
    lotti = {sku: lotto for sku in skus if (lotto := db.fetch_ultimo_lotto(sku)) is not None}
    gtins = {sku: gtin for sku in skus if (gtin := db.fetch_gtin(sku)) is not None}
    pdf = make_inner_labels_pdf(order_number, ordine["cliente"], result, lotti, gtins)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etichette_colli_{order_number}.pdf"'},
    )


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

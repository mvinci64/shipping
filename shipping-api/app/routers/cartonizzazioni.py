import datetime
import re

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import db
from app.cartonize import cartonize_order
from app.day_plan import make_day_plan_pdf
from app.labels import make_carton_summary_labels_pdf, make_gift_label_pdf, make_inner_labels_pdf

router = APIRouter()


class RigaOrdine(BaseModel):
    sku: str
    qta: float


class RichiestaCartonizzazione(BaseModel):
    order_number: str
    cliente: str = ""
    righe: list[RigaOrdine]


class ComponenteCollo(BaseModel):
    sku: str
    pezzi: int


class ScatolaInterna(BaseModel):
    # formato None per gli SKU sfusi (vedi cartonize.SFUSO_SKUS): niente
    # scatola interna, i pezzi riempiono lo scatolone direttamente.
    # sku None + componenti valorizzato per i colli misti (più SKU nella
    # stessa scatola interna, vedi cartonize.collo_misto_box).
    formato: str | None
    sku: str | None
    pezzi: int
    peso_g: int
    componenti: list[ComponenteCollo] | None = None


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


def _cartonize_ordine_reale(order_number: str, righe: list[dict]) -> dict:
    """cartonize_order con i colli misti manuali già registrati per
    l'ordine (sql/colli_misti_manuali.sql) — usarla SEMPRE al posto di
    cartonize_order() diretta per un ordine reale, altrimenti le quantità
    dei colli misti vengono contate due volte (auto + manuale) o segnalate
    come non censite."""
    try:
        return cartonize_order(righe, colli_misti=db.fetch_colli_misti_per_cartonize(order_number))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
    result = _cartonize_ordine_reale(order_number, ordine["righe"])
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
    result = _cartonize_ordine_reale(order_number, ordine["righe"])
    return RisultatoCartonizzazione(order_number=order_number, **result)


@router.get("/cartonizzazioni/{order_number}/etichette-colli")
def etichette_colli_ordine_reale(order_number: str, con_lotto: bool = False) -> Response:
    """Etichette collo (WP50/WP40) per un ordine reale, letto dal DB.

    con_lotto=false (default, deciso dall'utente 07/09/2026): lotto/scadenza
    non sono determinabili in modo affidabile (easyfatt.tmovmagazz è scritta
    da un ETL lanciato a mano, senza orario fisso — vedi Sprint 3 in
    piano-sprint.md), quindi vengono omessi sempre dall'etichetta collo. Il
    barcode resta comunque (GTIN da solo, senza lotto): identifica il
    prodotto anche senza lotto/scadenza. con_lotto=true resta disponibile
    per chi lo richiede esplicitamente, ma non è più il comportamento di
    default della UI."""
    ordine = _ordine_reale(order_number)
    result = _cartonize_ordine_reale(order_number, ordine["righe"])
    # item["sku"] è None per i colli misti (più SKU insieme, vedi
    # cartonize.collo_misto_box): i loro componenti vanno raccolti a parte.
    skus = {item["sku"] for carton in result["scatoloni"] for item in carton["contenuto"] if item["sku"]}
    skus |= {
        comp["sku"]
        for carton in result["scatoloni"] for item in carton["contenuto"]
        for comp in item.get("componenti") or []
    }
    nomi = {sku: nome for sku in skus if (nome := db.fetch_nome_prodotto(sku)) is not None}
    gtins = {sku: gtin for sku in skus if (gtin := db.fetch_gtin(sku)) is not None}
    lotti = {}
    if con_lotto:
        lotti = {sku: lotto for sku in skus if (lotto := db.fetch_ultimo_lotto(sku)) is not None}
    note_omaggio = [co["nota"] for co in db.fetch_colli_omaggio(order_number)]
    pdf = make_inner_labels_pdf(
        order_number, ordine["cliente"], result, lotti, gtins, nomi,
        mostra_lotto=con_lotto, note_omaggio=note_omaggio,
    )
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
    result = _cartonize_ordine_reale(order_number, ordine["righe"])
    pdf = make_carton_summary_labels_pdf(order_number, ordine["cliente"], ordine.get("data_consegna"), result)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etichette_scatolone_{order_number}.pdf"'},
    )


@router.get("/cartonizzazioni/{order_number}/etichetta-omaggio")
def etichetta_omaggio_ordine_reale(order_number: str, n: int = 1) -> Response:
    """Etichetta collo per omaggi/promozioni (WP40), stampa isolata: non è
    legata a una riga d'ordine, solo cliente + dicitura generica. n copie
    per più WP40 omaggio sullo stesso ordine. Per farla uscire insieme alle
    altre etichette collo dell'ordine (con una nota testuale), registrare
    invece un collo omaggio con POST /cartonizzazioni/{order_number}/colli-omaggio
    — vedi etichette_colli_ordine_reale."""
    ordine = _ordine_reale(order_number)
    pdf = make_gift_label_pdf(order_number, ordine["cliente"], n_etichette=n)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="etichetta_omaggio_{order_number}.pdf"'},
    )


class RichiestaColloOmaggio(BaseModel):
    nota: str


class ColloOmaggio(BaseModel):
    id: str
    order_number: str
    nota: str


@router.post("/cartonizzazioni/{order_number}/colli-omaggio", response_model=ColloOmaggio)
def aggiungi_collo_omaggio(order_number: str, richiesta: RichiestaColloOmaggio) -> ColloOmaggio:
    """Registra un collo omaggio/promozione (WP40 aggiunto a mano dal
    reparto, non da una riga d'ordine): la nota finisce stampata insieme
    alle altre etichette collo dell'ordine (etichette-colli), non serve una
    stampa separata."""
    collo = db.aggiungi_collo_omaggio(order_number, richiesta.nota)
    return ColloOmaggio(**collo)


@router.get("/cartonizzazioni/{order_number}/colli-omaggio", response_model=list[ColloOmaggio])
def elenco_colli_omaggio(order_number: str) -> list[ColloOmaggio]:
    return [ColloOmaggio(order_number=order_number, **co) for co in db.fetch_colli_omaggio(order_number)]


@router.delete("/cartonizzazioni/colli-omaggio/{collo_id}", status_code=204)
def rimuovi_collo_omaggio(collo_id: str) -> None:
    if not db.elimina_collo_omaggio(collo_id):
        raise HTTPException(status_code=404, detail=f"Collo omaggio {collo_id} non trovato")


class RichiestaColloMisto(BaseModel):
    # None = gruppo sfuso a scatolone forzato (vedi
    # sql/colli_misti_manuali_sfuso_indice.sql, 01/10/2026) — richiede
    # scatolone_indice. "WP50"/"WP40" = collo misto normale (scatola
    # interna), scatolone_indice non si applica.
    formato: str | None = None
    componenti: list[ComponenteCollo]
    scatolone_indice: int | None = None


class ColloMisto(BaseModel):
    id: str
    order_number: str
    formato: str | None
    contenuto: list[ComponenteCollo]
    scatolone_indice: int | None = None


@router.post("/cartonizzazioni/{order_number}/colli-misti", response_model=ColloMisto)
def aggiungi_collo_misto(order_number: str, richiesta: RichiestaColloMisto) -> ColloMisto:
    """Registra un collo con più SKU insieme (WP40/WP50), deciso a mano dal
    reparto quando i prodotti coinvolti non sono censiti singolarmente —
    vedi cartonize.SFUSO_SKUS/GRAMMATURA_G e sql/colli_misti_manuali.sql.
    Le quantità dei componenti sono validate contro le righe reali
    dell'ordine (non possono superare quanto ordinato, sommato agli altri
    colli misti già registrati) prima di salvare.

    formato=None richiede scatolone_indice valorizzato: registra un gruppo
    sfuso (niente scatola interna) piazzato a mano in quello scatolone del
    risultato automatico — caso reale ORD-20260924-6100 (01/10/2026), torte
    caprese spostate in uno scatolone che l'algoritmo considererebbe
    "pieno" per posti, ma che il reparto ha verificato entrarci fisicamente.
    Vedi cartonize.cartonize_order e sql/colli_misti_manuali_sfuso_indice.sql."""
    if richiesta.formato not in ("WP50", "WP40", None):
        raise HTTPException(status_code=422, detail="formato deve essere 'WP50', 'WP40' o assente (gruppo sfuso)")
    if richiesta.formato is None and not richiesta.scatolone_indice:
        raise HTTPException(status_code=422, detail="scatolone_indice obbligatorio per un gruppo sfuso (formato assente)")
    if richiesta.formato is not None and richiesta.scatolone_indice:
        raise HTTPException(status_code=422, detail="scatolone_indice si applica solo ai gruppi sfusi (formato assente)")
    ordine = _ordine_reale(order_number)
    esistenti = db.fetch_colli_misti_per_cartonize(order_number) or []
    nuovo = {
        "formato": richiesta.formato,
        "componenti": [c.model_dump() for c in richiesta.componenti],
        "scatolone_indice": richiesta.scatolone_indice,
    }
    try:
        cartonize_order(ordine["righe"], colli_misti=esistenti + [nuovo])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Peso non censito per SKU {exc}") from exc

    creato = db.aggiungi_collo_misto(order_number, richiesta.formato, nuovo["componenti"], richiesta.scatolone_indice)
    return ColloMisto(**creato)


@router.get("/cartonizzazioni/{order_number}/colli-misti", response_model=list[ColloMisto])
def elenco_colli_misti(order_number: str) -> list[ColloMisto]:
    """Colli misti già registrati per un ordine."""
    return [ColloMisto(order_number=order_number, **cm) for cm in db.fetch_colli_misti(order_number)]


@router.delete("/cartonizzazioni/colli-misti/{collo_id}", status_code=204)
def rimuovi_collo_misto(collo_id: str) -> None:
    """Annulla un collo misto (errore di battitura, cambio di piano)."""
    if not db.elimina_collo_misto(collo_id):
        raise HTTPException(status_code=404, detail=f"Collo misto {collo_id} non trovato")


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

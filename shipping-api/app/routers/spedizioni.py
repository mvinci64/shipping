import base64
import datetime
import re

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import db, dhl
from app.routers.cartonizzazioni import _cartonize_ordine_reale, _stato_colli

router = APIRouter()


class SpedizioneResponse(BaseModel):
    id: str
    order_number: str
    # Altri ordini dello stesso destinatario consolidati in questa unica
    # spedizione DHL (vuoto per le spedizioni a ordine singolo, che
    # restano il caso normale) — vedi sql/spedizioni_consolidate.sql.
    ordini_aggregati: list[str] = []
    # None nel caso normale (pesi dalla cartonizzazione); valorizzato se
    # il reparto ha dichiarato a mano i pacchi reali — vedi
    # sql/spedizioni_colli_dichiarati.sql.
    colli_dichiarati: list[dict] | None = None
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
    contrassegno_eur: float | None = None

# customers.country nel DB del Portal è incoerente: alcuni clienti hanno il
# nome esteso ("Italia", 109 su 166 attivi), altri già il codice ISO2 ("IT",
# 58 su 166), altri il nome esteso di un altro paese ("Svezia"). MyDHL API
# vuole sempre ISO2. Mappa minima per i nomi estesi noti: si estende quando
# arrivano nuovi paesi reali.
PAESE_ISO2 = {"italia": "IT", "svezia": "SE"}

# customers.shipping_address ha due formati osservati sul DB reale:
# "Via Rossi 1, 18035" (CAP in coda) e "NOME VIA STRADA N 20900 CITTÀ (PROV)"
# (CAP in mezzo, seguito da città/provincia — 12 clienti su 166 attivi,
# es. "DROGHERIA CIRLA VIA ZUCCHI 14 20900 MONZA (MB)"). Cerca un token di
# 5 cifre isolato ovunque nella stringa, non solo in coda.
CAP_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)")


def _estrai_cap(indirizzo: str) -> str:
    match = CAP_RE.search(indirizzo or "")
    if not match:
        raise HTTPException(
            status_code=422,
            detail=f"CAP non trovato nell'indirizzo: {indirizzo!r}",
        )
    return match.group(1)


def _cap_destinatario(destinatario: dict) -> str:
    """customers.cap (colonna dedicata, aggiunta 04/09/2026) se
    valorizzata; altrimenti fallback sul parsing di shipping_address —
    resta utile per i pochi clienti non ancora coperti dal backfill."""
    return destinatario.get("cap") or _estrai_cap(destinatario["indirizzo"])


# Coda "<CAP> <CITTÀ> (<PROV>)" di shipping_address, es.
# "GLI AMICI DEL GALLI VIA SAN GIUSEPPE 18 21047 SARONNO (VA)".
DESTINAZIONE_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)\s+(.+?)\s*\(\s*([A-Za-z]{2})\s*\)\s*$")


def _destinazione(destinatario: dict) -> tuple[str, str, str]:
    """CAP, città e provincia da mandare al corriere — (cap, citta, prov).

    Normalmente vengono da customers (cap/city/province). Ma quelle
    colonne descrivono la SEDE del cliente, mentre shipping_address è la
    destinazione merce: quando le due differiscono davvero, prenderle da
    fonti diverse produce un indirizzo ibrido. Caso reale GLI AMICI DEL
    GALLI (IMPORT-DMLAB-20261027-01, 28/10/2026): via di Saronno (VA) con
    CAP, città e provincia di Turate (CO), due comuni e due province
    diverse — segnalato dal team del Portal, il cui import popola
    customers.cap dal CustomerPostcode della sede legale.

    Regola: si usa la destinazione di shipping_address — tutta intera,
    CAP+città+provincia insieme, mai mischiata con l'anagrafica — solo
    quando da quel testo si legge una destinazione completa che differisce
    dall'anagrafica SIA per città SIA per CAP. In ogni altro caso resta il
    comportamento di sempre.

    Servono entrambe le condizioni, per due motivi distinti misurati sui
    121 ordini in prenotazione (28/10/2026):

    - città diversa ma stesso CAP non è un'altra destinazione, è un altro
      NOME dello stesso posto, e cambiarlo non migliora l'instradamento
      (DHL instrada sul CAP) mentre rischia un rifiuto per città non
      valida per quel CAP. Casi reali: IL CORAZZIERE "22046 BAGGERO"
      contro MERONE in anagrafica (Baggero è una frazione di Merone), e
      PALLARO ENRICO "21100 VARESE" contro VIGGIU.
    - CAP diverso ma stessa città è quasi sempre un dato sbagliato nel
      testo libero: PASTICCERIA ERNANI (IMPORT-DMLAB-20260706-01) riporta
      22070 per LURATE CACCIVIO, il cui CAP reale è 22075 come in
      anagrafica. Fidarsi del CAP parsato avrebbe spedito sul CAP errato.

    Con entrambe le condizioni l'unico ordine che cambia comportamento è
    proprio GLI AMICI DEL GALLI."""
    citta_anagrafica = (destinatario.get("citta") or "").strip()
    prov_anagrafica = (destinatario.get("provincia") or "").strip()
    cap_corrente = _cap_destinatario(destinatario)

    match = DESTINAZIONE_RE.search(destinatario.get("indirizzo") or "")
    if match:
        cap_sped, citta_sped, prov_sped = match.group(1), match.group(2).strip(), match.group(3).upper()
        citta_diversa = bool(citta_sped) and citta_sped.casefold() != citta_anagrafica.casefold()
        cap_diverso = cap_sped != cap_corrente
        if citta_diversa and cap_diverso:
            return cap_sped, citta_sped, prov_sped

    return cap_corrente, citta_anagrafica, prov_anagrafica


# Prefissi di via noti, per tagliare via il nome azienda quando precede la
# via nel formato "NOME VIA STRADA N CAP CITTÀ (PROV)" (vedi commento sopra
# CAP_RE). Elenco minimo, esteso quando emerge un caso reale non coperto.
_PREFISSI_VIA = (
    "via", "viale", "v.le", "corso", "c.so", "piazza", "p.zza", "p.za",
    "vicolo", "largo", "strada", "s.da", "c.da", "contrada", "località",
    "localita", "loc.", "frazione", "fraz.", "lungomare", "lungarno",
)


def _indirizzo_spedizione(indirizzo: str) -> str:
    """Solo la via, ripulita da CAP/città/provincia ed eventuale nome
    azienda in testa — MyDHL API vuole addressLine1 lungo al massimo 45
    caratteri, ma customers.shipping_address è testo libero con tutto
    insieme (es. "STELMOKA VIA VITTORIO EMANUELE II 11/13 20842 BESANA IN
    BRIANZA (MB)", 68 caratteri: 422 "expected maxLength: 45, actual: 68"
    da DHL su IMPORT-DMLAB-20260629-01, 15/09/2026). Troncamento finale a
    45 come rete di sicurezza, anche se l'estrazione qui sopra fallisse."""
    grezzo = (indirizzo or "").strip()
    match = CAP_RE.search(grezzo)
    prima_del_cap = (grezzo[: match.start()] if match else grezzo).strip(" ,")

    parole = prima_del_cap.split()
    for i, parola in enumerate(parole):
        if parola.strip(".").lower() in _PREFISSI_VIA:
            prima_del_cap = " ".join(parole[i:])
            break

    return (prima_del_cap or grezzo)[:45].strip()


def _iso2(paese: str) -> str:
    paese_pulito = (paese or "").strip()
    if len(paese_pulito) == 2 and paese_pulito.isalpha():
        return paese_pulito.upper()
    codice = PAESE_ISO2.get(paese_pulito.lower())
    if codice is None:
        raise HTTPException(
            status_code=422,
            detail=f"Paese '{paese}' non mappato a un codice ISO2 (vedi PAESE_ISO2 in spedizioni.py)",
        )
    return codice


def _prossima_data_spedizione() -> str:
    """Oggi, o il prossimo giorno feriale se oggi è sabato/domenica — DHL
    risponde 404 "product not available for the requested pickup date" su
    /rates e /shipments per una data di weekend (nessun ritiro festivi
    italiani: da rivedere se emerge un caso reale)."""
    giorno = datetime.date.today()
    while giorno.weekday() >= 5:
        giorno += datetime.timedelta(days=1)
    return giorno.isoformat()


def _ordine_e_destinatario(order_number: str) -> tuple[dict, dict]:
    ordine = db.fetch_order(order_number)
    if ordine is None:
        raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
    return ordine, db.fetch_destinatario(order_number)


def _contrassegno_eur(order_number: str, ordine: dict) -> float | None:
    """Importo da richiedere in contrassegno alla consegna, o None se
    l'ordine è già pagato in anticipo. Stessa logica della vista Ordini del
    Portal (CASE WHEN payment_advance_discount THEN 'Anticipo' ELSE
    'Contrassegno' END, confermata dall'utente 18/09/2026): nessuna colonna
    dedicata "modalità di pagamento", solo questi due casi — NULL si
    comporta come False (contrassegno). dhl.crea_spedizione aggiunge il
    servizio contrassegno (KB) sulla spedizione, così il corriere non
    rilascia la merce senza prima incassare."""
    if ordine["payment_advance_discount"]:
        return None
    if ordine["grand_total"] is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Ordine {order_number} non pagato in anticipo (contrassegno) ma senza grand_total: "
                "impossibile determinare l'importo da richiedere alla consegna"
            ),
        )
    return ordine["grand_total"]


def _pesi_scatoloni_kg(order_number: str, ordine: dict) -> list[float]:
    """Usa SEMPRE _cartonize_ordine_reale (colli misti manuali inclusi):
    cartonize_order() diretta ignora i colli misti registrati per l'ordine
    e sottostima peso/numero scatoloni della spedizione DHL reale — bug
    scoperto il 18/09/2026 preparando ORD-20260505-4944 (VP01/VP02/VP04/
    VP05/VP06 non hanno un PEZZI_PER_COLLO proprio, quindi senza i colli
    misti finivano silenziosamente in non_censiti e sparivano dal peso)."""
    cartonizzazione = _cartonize_ordine_reale(order_number, ordine["righe"])
    if cartonizzazione["n_scatoloni"] == 0:
        raise HTTPException(status_code=422, detail="Nessuno scatolone: ordine senza prodotti censiti")
    return [round(c["peso_g"] / 1000, 3) for c in cartonizzazione["scatoloni"]]


def _quota(destinatario: dict, pesi_kg: list[float], data_iso: str) -> dict:
    cap_dest, citta_dest, prov_dest = _destinazione(destinatario)
    try:
        return dhl.valida_spedizione(
            destinatario_cap=cap_dest,
            destinatario_citta=citta_dest,
            destinatario_provincia=prov_dest,
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
    pesi_kg = _pesi_scatoloni_kg(order_number, ordine)
    risposta_dhl = _quota(destinatario, pesi_kg, _prossima_data_spedizione())
    return {
        "order_number": order_number,
        "n_scatoloni": len(pesi_kg),
        "pesi_scatoloni_kg": pesi_kg,
        "contrassegno_eur": _contrassegno_eur(order_number, ordine),
        "dhl": risposta_dhl,
    }


def _valida_consolidamento(capofila: str, ordini_aggregati: list[str]) -> None:
    """Controlli obbligatori prima di consolidare più ordini in un'unica
    spedizione DHL (vedi sql/spedizioni_consolidate.sql). Solleva 409/422
    se il consolidamento non è lecito: una spedizione unica significa UNA
    etichetta, UN indirizzo e UN ritiro, quindi gli ordini devono essere
    dello stesso cliente e partire insieme."""
    if len(set(ordini_aggregati)) != len(ordini_aggregati):
        raise HTTPException(status_code=422, detail="ordini_aggregati contiene duplicati")
    if capofila in ordini_aggregati:
        raise HTTPException(
            status_code=422,
            detail=f"L'ordine capofila {capofila} non va ripetuto in ordini_aggregati",
        )

    tutti = [capofila, *ordini_aggregati]
    dati = db.fetch_dati_consolidamento(tutti)
    trovati = {d["order_number"] for d in dati}
    mancanti = [o for o in tutti if o not in trovati]
    if mancanti:
        raise HTTPException(status_code=404, detail=f"Ordini non trovati: {', '.join(mancanti)}")

    # Stesso cliente: si confronta customer_id, non il nome azienda —
    # vedi db.fetch_dati_consolidamento per il perché.
    clienti = {d["customer_id"] for d in dati}
    if len(clienti) > 1:
        raise HTTPException(
            status_code=422,
            detail=(
                "Gli ordini da consolidare non sono dello stesso cliente: una spedizione "
                "unica ha un solo destinatario. Ordini: "
                + ", ".join(f"{d['order_number']} (cliente {d['customer_id']})" for d in dati)
            ),
        )

    date = {d["data_consegna"] for d in dati}
    if len(date) > 1:
        raise HTTPException(
            status_code=422,
            detail=(
                "Gli ordini da consolidare hanno date di consegna diverse ("
                + ", ".join(f"{d['order_number']}: {d['data_consegna']}" for d in dati)
                + "): una spedizione unica parte in un solo giorno"
            ),
        )

    # Un ordine già in viaggio (o con una bozza aperta) non può essere
    # assorbito in una nuova spedizione: si pagherebbe due volte lo stesso
    # ordine, o si lascerebbe una bozza orfana.
    for ordine_numero in tutti:
        esistente = db.fetch_ultima_spedizione_per_ordine(ordine_numero)
        if esistente is not None and esistente["stato"] in ("bozza", "confermata", "ritirata"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"L'ordine {ordine_numero} ha già una spedizione in stato "
                    f"'{esistente['stato']}' (id {esistente['id']}): annullarla prima di "
                    "consolidarlo in una nuova spedizione"
                ),
            )


def _pesi_e_riferimenti(ordini: list[str]) -> tuple[list[float], list[str]]:
    """Pesi di tutti gli scatoloni degli ordini indicati, con accanto
    l'ordine di appartenenza di ciascun collo (liste parallele). Per una
    spedizione consolidata i colli dei vari ordini restano colli distinti:
    non si rimescola la cartonizzazione, si somma solo ciò che parte
    insieme — così ogni collo può portare il riferimento del proprio
    ordine sull'etichetta DHL (vedi dhl.crea_spedizione)."""
    pesi: list[float] = []
    riferimenti: list[str] = []
    for order_number in ordini:
        ordine = db.fetch_order(order_number)
        if ordine is None:
            raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
        pesi_ordine = _pesi_scatoloni_kg(order_number, ordine)
        pesi += pesi_ordine
        riferimenti += [order_number] * len(pesi_ordine)
    return pesi, riferimenti


def _contrassegno_totale(ordini: list[str]) -> float | None:
    """Contrassegno complessivo di una spedizione: somma degli importi
    degli ordini che lo prevedono, None se sono tutti già pagati. Il
    corriere riscuote una volta sola alla consegna, quindi su una
    spedizione consolidata deve riscuotere il TOTALE — chiedere solo
    l'importo del capofila significherebbe consegnare merce non pagata."""
    importi = []
    for order_number in ordini:
        ordine = db.fetch_order(order_number)
        if ordine is None:
            raise HTTPException(status_code=404, detail=f"Ordine {order_number} non trovato")
        importo = _contrassegno_eur(order_number, ordine)
        if importo is not None:
            importi.append(importo)
    return round(sum(importi), 2) if importi else None


class ColloDichiarato(BaseModel):
    """Un pacco FISICO realmente spedito, dichiarato dal reparto quando
    l'impacchettamento reale non segue la regola dei 6 posti."""
    peso_kg: float
    # Ordini la cui merce è dentro questo pacco: finiscono come
    # riferimenti sull'etichetta DHL del collo. Più di uno quando il
    # pacco contiene merce di ordini diversi (spedizione consolidata).
    ordini: list[str]


def _valida_colli_dichiarati(
    colli: list[ColloDichiarato], ordini_spedizione: list[str], peso_calcolato_kg: float,
) -> None:
    """Controlli sui pacchi dichiarati a mano. Qui si sta sostituendo il
    calcolo con un dato umano su una spedizione a costo reale, quindi i
    controlli servono a intercettare gli errori di battitura prima che
    diventino un'etichetta DHL sbagliata."""
    if not colli:
        raise HTTPException(status_code=422, detail="colli_dichiarati non può essere vuoto")
    for i, collo in enumerate(colli, 1):
        if collo.peso_kg <= 0:
            raise HTTPException(status_code=422, detail=f"Collo {i}: peso_kg deve essere positivo")
        if not collo.ordini:
            raise HTTPException(
                status_code=422,
                detail=f"Collo {i}: indicare almeno un ordine (serve per il riferimento sull'etichetta)",
            )
        estranei = [o for o in collo.ordini if o not in ordini_spedizione]
        if estranei:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Collo {i}: gli ordini {', '.join(estranei)} non fanno parte di questa "
                    f"spedizione (ordini della spedizione: {', '.join(ordini_spedizione)})"
                ),
            )

    # Ogni ordine della spedizione deve stare in almeno un pacco: se un
    # ordine non è in nessun collo, la sua merce non risulta spedita da
    # nessuna parte e la sua etichetta non verrebbe stampata.
    coperti = {o for collo in colli for o in collo.ordini}
    scoperti = [o for o in ordini_spedizione if o not in coperti]
    if scoperti:
        raise HTTPException(
            status_code=422,
            detail=f"Nessun collo dichiarato contiene gli ordini: {', '.join(scoperti)}",
        )

    # Il peso totale dichiarato non può scostarsi troppo dal calcolato: un
    # po' di differenza è normale (meno scatoloni = meno tara e carta), ma
    # un fattore 2 è quasi sempre un errore di digitazione, e il peso è
    # ciò su cui DHL fattura.
    peso_dichiarato = sum(c.peso_kg for c in colli)
    if peso_calcolato_kg > 0 and not (
        0.5 * peso_calcolato_kg <= peso_dichiarato <= 1.5 * peso_calcolato_kg
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Peso dichiarato {round(peso_dichiarato, 2)} kg troppo distante dal calcolato "
                f"{round(peso_calcolato_kg, 2)} kg (atteso entro ±50%): verificare i pesi inseriti"
            ),
        )


@router.post("/spedizioni", response_model=SpedizioneResponse)
def crea_bozza_spedizione(
    order_number: str,
    ordini_aggregati: list[str] | None = None,
    colli_dichiarati: list[ColloDichiarato] | None = None,
) -> SpedizioneResponse:
    """Crea la bozza (stato 'bozza'): quota via /rates e salva su DB.
    Nessuna chiamata DHL con effetto reale — solo /rates, come /valida.

    ordini_aggregati: altri ordini dello STESSO cliente e con la STESSA
    data di consegna da spedire in un'unica spedizione DHL (un collo
    fisico, un'etichetta, un ritiro) — caso reale STREGATE TEA SHOP con
    due ordini separati, 21/10/2026. order_number fa da capofila; pesi e
    contrassegno della bozza sono quelli di tutti gli ordini insieme.
    Vedi _valida_consolidamento per i controlli applicati."""
    aggregati = ordini_aggregati or []
    if aggregati:
        _valida_consolidamento(order_number, aggregati)

    ordine, destinatario = _ordine_e_destinatario(order_number)
    tutti_gli_ordini = [order_number, *aggregati]
    pesi_calcolati, _riferimenti = _pesi_e_riferimenti(tutti_gli_ordini)

    if colli_dichiarati:
        _valida_colli_dichiarati(colli_dichiarati, tutti_gli_ordini, sum(pesi_calcolati))
        pesi_kg = [c.peso_kg for c in colli_dichiarati]
        dichiarati = [c.model_dump() for c in colli_dichiarati]
    else:
        pesi_kg = pesi_calcolati
        dichiarati = None

    risposta_dhl = _quota(destinatario, pesi_kg, _prossima_data_spedizione())
    product_code, prezzo = _scegli_prodotto(risposta_dhl)
    bozza = db.crea_spedizione_bozza(
        order_number=order_number, corriere="dhl", product_code=product_code,
        pesi_scatoloni_kg=pesi_kg, prezzo_stimato_eur=prezzo,
        ordini_aggregati=aggregati, colli_dichiarati=dichiarati,
    )
    return SpedizioneResponse(**bozza, contrassegno_eur=_contrassegno_totale(tutti_gli_ordini))


class OrdineConsolidabile(BaseModel):
    order_number: str
    data_consegna: str | None
    n_colli: int


@router.get("/spedizioni/consolidabili/{order_number}", response_model=list[OrdineConsolidabile])
def ordini_consolidabili(order_number: str) -> list[OrdineConsolidabile]:
    """Altri ordini che si possono spedire nella stessa spedizione DHL di
    questo (stesso cliente, stessa data di consegna, nessuna spedizione
    già aperta) — vedi POST /spedizioni con ordini_aggregati. Lista vuota
    nel caso normale di un cliente con un solo ordine in partenza.
    Sola lettura, nessun effetto."""
    risultato = []
    for candidato in db.fetch_ordini_consolidabili(order_number):
        ordine = db.fetch_order(candidato["order_number"])
        if ordine is None:
            continue
        cartonizzazione = _cartonize_ordine_reale(candidato["order_number"], ordine["righe"])
        risultato.append(OrdineConsolidabile(
            order_number=candidato["order_number"],
            data_consegna=candidato["data_consegna"],
            n_colli=cartonizzazione["n_scatoloni"],
        ))
    return risultato


class RigaElenco(BaseModel):
    order_number: str
    cliente: str
    data_consegna: str | None
    n_colli: int
    colli_confermati: int
    colli_completo: bool
    spedizione_stato: str  # 'non_iniziata' | 'bozza' | 'confermata' | 'ritirata' | 'fallita'
    spedizione_id: str | None
    # Valorizzato solo se questo ordine viaggia in una spedizione
    # CONSOLIDATA di cui NON è il capofila: contiene il numero d'ordine
    # capofila, così il reparto vede che la merce parte già (sotto
    # un'altra spedizione) invece di credere che manchi.
    spedizione_capofila: str | None = None


@router.get("/spedizioni/elenco", response_model=list[RigaElenco])
def elenco_spedizioni(
    data_da: datetime.date | None = None, data_a: datetime.date | None = None,
) -> list[RigaElenco]:
    """Vista d'insieme, sola lettura: tutti gli ordini "in prenotazione" nel
    periodo (default: oggi + 13 giorni, due settimane), con lo stato dei
    colli scansionati e della spedizione — se esiste già una bozza/una
    conferma. Nessuna azione qui: solo per farsi un'idea di cosa c'è da
    processare, prima di agire con le chiamate dedicate."""
    oggi = datetime.date.today()
    data_da = data_da or oggi
    data_a = data_a or (oggi + datetime.timedelta(days=13))
    if data_a < data_da:
        raise HTTPException(status_code=422, detail="data_a precedente a data_da")

    righe = []
    for ordine in db.fetch_elenco_spedizioni(data_da, data_a):
        cartonizzazione = _cartonize_ordine_reale(ordine["order_number"], ordine["righe"])
        n_colli = cartonizzazione["n_scatoloni"]
        confermati = ordine["colli_confermati"]
        spedizione = ordine["spedizione"]
        righe.append(RigaElenco(
            order_number=ordine["order_number"],
            cliente=ordine["cliente"],
            data_consegna=ordine.get("data_consegna"),
            n_colli=n_colli,
            colli_confermati=len(confermati),
            colli_completo=n_colli > 0 and len(confermati) >= n_colli,
            spedizione_stato=spedizione["stato"] if spedizione else "non_iniziata",
            spedizione_id=spedizione["id"] if spedizione else None,
            spedizione_capofila=(
                spedizione["order_number"]
                if spedizione and spedizione["order_number"] != ordine["order_number"]
                else None
            ),
        ))
    return righe


class EventoTracking(BaseModel):
    data: str
    descrizione: str


class RigaTracking(BaseModel):
    order_number: str
    cliente: str
    data_consegna: str | None
    stato: str  # 'confermata' | 'ritirata' (FSM nostra, non DHL)
    shipment_tracking_number: str
    dispatch_confirmation_number: str | None
    tracking_url: str | None
    stato_dhl: str | None
    consegna_stimata: str | None
    eventi: list[EventoTracking]
    errore: str | None


@router.get("/spedizioni/tracking", response_model=list[RigaTracking])
def tracking_spedizioni(
    data_da: datetime.date | None = None, data_a: datetime.date | None = None,
) -> list[RigaTracking]:
    """Stato di tracciamento DHL reale (sola lettura, nessun effetto) per
    tutte le spedizioni confermate/ritirate con consegna richiesta nel
    periodo (default: oggi + 13 giorni). Una chiamata a DHL per spedizione
    — se una fallisce (es. tracking non ancora propagato appena dopo la
    conferma) le altre righe restano comunque valorizzate, l'errore va
    nel campo `errore` di quella riga soltanto."""
    oggi = datetime.date.today()
    data_da = data_da or oggi
    data_a = data_a or (oggi + datetime.timedelta(days=13))
    if data_a < data_da:
        raise HTTPException(status_code=422, detail="data_a precedente a data_da")

    righe = []
    for s in db.fetch_spedizioni_tracciabili(data_da, data_a):
        try:
            tracking = dhl.traccia_spedizione(s["shipment_tracking_number"])
            stato_dhl, consegna_stimata, eventi, errore = (
                tracking["stato"], tracking["consegna_stimata"], tracking["eventi"], None,
            )
        except (dhl.DHLConfigError, dhl.DHLAPIError) as exc:
            stato_dhl, consegna_stimata, eventi, errore = None, None, [], str(exc)
        righe.append(RigaTracking(
            order_number=s["order_number"], cliente=s["cliente"], data_consegna=s["data_consegna"],
            stato=s["stato"], shipment_tracking_number=s["shipment_tracking_number"],
            dispatch_confirmation_number=s["dispatch_confirmation_number"], tracking_url=s["tracking_url"],
            stato_dhl=stato_dhl, consegna_stimata=consegna_stimata, eventi=eventi, errore=errore,
        ))
    return righe


def _con_contrassegno(spedizione: dict) -> SpedizioneResponse:
    """Contrassegno da mostrare per una spedizione già esistente: il
    TOTALE di tutti i suoi ordini, così una spedizione consolidata non
    espone l'importo del solo capofila (l'operatore lo leggerebbe come
    cifra da riscuotere, ed è quella sbagliata)."""
    return SpedizioneResponse(
        **spedizione,
        contrassegno_eur=_contrassegno_totale(db.ordini_di_spedizione(spedizione)),
    )


@router.get("/spedizioni/per-ordine/{order_number}", response_model=SpedizioneResponse | None)
def spedizione_per_ordine(order_number: str) -> SpedizioneResponse | None:
    """Spedizione più recente per un ordine, o null se non è mai stata
    creata una bozza — non è un errore, è lo stato "da iniziare". Usato
    dalla pagina di dettaglio ordine, che non ha altrimenti modo di
    risalire allo spedizione_id partendo dal solo order_number."""
    spedizione = db.fetch_ultima_spedizione_per_ordine(order_number)
    return _con_contrassegno(spedizione) if spedizione else None


@router.get("/spedizioni/{spedizione_id}", response_model=SpedizioneResponse)
def dettaglio_spedizione(spedizione_id: str) -> SpedizioneResponse:
    spedizione = db.fetch_spedizione(spedizione_id)
    if spedizione is None:
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata")
    return _con_contrassegno(spedizione)


@router.post("/spedizioni/{spedizione_id}/conferma", response_model=SpedizioneResponse)
def conferma_spedizione(spedizione_id: str) -> SpedizioneResponse:
    """bozza -> confermata. QUESTA CHIAMATA HA EFFETTO REALE: crea la
    spedizione DHL vera con relativo costo (dhl.crea_spedizione). Va
    invocata solo dopo controllo umano della bozza (GET /spedizioni/{id}).

    Gate: rifiuta (409) se il reparto non ha ancora scansionato tutti i
    colli dell'ordine (vedi POST /cartonizzazioni/colli/conferma) — senza
    questo controllo si potrebbe confermare (costo reale, ritiro reale)
    una spedizione con uno scatolone ancora aperto sul tavolo.

    Accetta anche stato 'fallita' (non solo 'bozza'): un tentativo
    precedente può fallire per un motivo nel frattempo corretto (es. dati
    destinatario) senza che sia mai stata creata una spedizione DHL reale
    — vedi db.segna_spedizione_fallita, non ha effetto lato DHL."""
    spedizione = db.fetch_spedizione(spedizione_id)
    if spedizione is None:
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata")
    if spedizione["stato"] not in ("bozza", "fallita"):
        raise HTTPException(
            status_code=409, detail=f"Spedizione in stato '{spedizione['stato']}', non 'bozza'/'fallita'"
        )

    # Il gate vale per OGNI ordine della spedizione, non solo per il
    # capofila: su una spedizione consolidata basterebbe altrimenti avere
    # i colli del capofila pronti per far partire (costo e ritiro reali)
    # una spedizione a cui manca ancora la merce del secondo ordine.
    ordini_spedizione = db.ordini_di_spedizione(spedizione)
    for ordine_numero in ordini_spedizione:
        stato_colli = _stato_colli(ordine_numero)
        if not stato_colli.completo:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Colli non ancora tutti confermati a fine linea per l'ordine "
                    f"{ordine_numero}: mancano {stato_colli.mancanti} "
                    f"su {stato_colli.n_totale} (vedi GET /cartonizzazioni/{ordine_numero}/colli)"
                ),
            )

    ordine, destinatario = _ordine_e_destinatario(spedizione["order_number"])
    if not _indirizzo_spedizione(destinatario["indirizzo"]):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Indirizzo mancante per il cliente dell'ordine {spedizione['order_number']} "
                "(né viscotta.customers.shipping_address né easyfatt.tanagrafica.indirizzo) — "
                "va aggiunto a mano prima di poter confermare"
            ),
        )

    if spedizione["colli_dichiarati"]:
        # Pacchi dichiarati a mano dal reparto (vedi
        # sql/spedizioni_colli_dichiarati.sql): sono un dato umano sui
        # pacchi FISICI, non vanno ricalcolati né confrontati con la
        # cartonizzazione — è proprio il caso in cui i due numeri
        # divergono di proposito.
        riferimenti_colli = [c["ordini"] for c in spedizione["colli_dichiarati"]]
    else:
        # I riferimenti per collo vanno ricalcolati dalla cartonizzazione
        # di adesso, ma i pesi su cui si è quotato (e che DHL fatturerà)
        # sono quelli salvati sulla bozza: se nel frattempo la
        # cartonizzazione è cambiata (un collo misto registrato dopo la
        # bozza, una capacità SKU censita nel frattempo) le due cose non
        # combaciano più e l'etichetta riporterebbe riferimenti sbagliati.
        # Meglio fermarsi e far ricreare la bozza che emettere una
        # spedizione reale incoerente.
        pesi_ora, riferimenti_per_collo = _pesi_e_riferimenti(ordini_spedizione)
        if pesi_ora != [float(p) for p in spedizione["pesi_scatoloni_kg"]]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "La cartonizzazione è cambiata dopo la creazione della bozza "
                    f"(bozza: {spedizione['pesi_scatoloni_kg']} kg, adesso: {pesi_ora} kg): "
                    "annullare questa bozza e ricrearla prima di confermare"
                ),
            )
        riferimenti_colli = [[o] for o in riferimenti_per_collo]

    cap_dest, citta_dest, prov_dest = _destinazione(destinatario)
    try:
        risposta = dhl.crea_spedizione(
            order_number=spedizione["order_number"],
            product_code=spedizione["product_code"],
            destinatario_nome=destinatario["nome"] or ordine["cliente"],
            destinatario_email=destinatario["email"] or "",
            destinatario_telefono=destinatario["telefono"] or "",
            destinatario_indirizzo=_indirizzo_spedizione(destinatario["indirizzo"]),
            destinatario_cap=cap_dest,
            destinatario_citta=citta_dest,
            destinatario_provincia=prov_dest,
            destinatario_paese=_iso2(destinatario["paese"]),
            pesi_scatoloni_kg=spedizione["pesi_scatoloni_kg"],
            data_spedizione_iso=_prossima_data_spedizione(),
            # Totale di tutti gli ordini della spedizione: il corriere
            # riscuote una volta sola alla consegna (vedi
            # _contrassegno_totale).
            contrassegno_eur=_contrassegno_totale(ordini_spedizione),
            # Ogni collo porta il riferimento del proprio ordine (allineato
            # ai pesi dal controllo qui sopra).
            riferimenti_colli=riferimenti_colli,
        )
    except (dhl.DHLConfigError, dhl.DHLAPIError) as exc:
        db.segna_spedizione_fallita(spedizione_id, errore=str(exc))
        status = 502 if isinstance(exc, dhl.DHLAPIError) else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    etichetta_b64 = risposta["documents"][0]["content"]
    tracking_number = risposta["shipmentTrackingNumber"]
    aggiornata = db.conferma_spedizione(
        spedizione_id,
        shipment_tracking_number=tracking_number,
        # NON risposta["trackingUrl"]: quello è l'URL dell'API DHL
        # (express.api.dhl.com/...), non la pagina pubblica di
        # tracciabilità che si può aprire nel browser.
        tracking_url=f"https://www.dhl.com/it-it/home/tracciabilita.html?tracking-id={tracking_number}&submit=1",
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


class RichiestaPickupMultiplo(BaseModel):
    spedizione_ids: list[str]
    data_pickup: datetime.date | None = None


@router.post("/spedizioni/pickup-multiplo", response_model=list[SpedizioneResponse])
def richiedi_pickup_multiplo(body: RichiestaPickupMultiplo) -> list[SpedizioneResponse]:
    """Come /spedizioni/{id}/pickup ma per PIÙ spedizioni insieme, con UN
    SOLO ritiro DHL (un solo passaggio del corriere, un solo PRG) invece di
    uno per spedizione — usarlo quando più ordini vanno ritirati lo stesso
    giorno. QUESTA CHIAMATA HA EFFETTO REALE: prenota il ritiro DHL vero
    per tutte le spedizioni elencate in un'unica chiamata."""
    if not body.spedizione_ids:
        raise HTTPException(status_code=422, detail="spedizione_ids non può essere vuoto")

    spedizioni = []
    for spedizione_id in body.spedizione_ids:
        spedizione = db.fetch_spedizione(spedizione_id)
        if spedizione is None:
            raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata")
        if spedizione["stato"] != "confermata":
            raise HTTPException(
                status_code=409,
                detail=f"Spedizione {spedizione_id} in stato '{spedizione['stato']}', non 'confermata'",
            )
        spedizioni.append(spedizione)

    data_iso = (body.data_pickup or (datetime.date.today() + datetime.timedelta(days=1))).isoformat()
    try:
        risposta = dhl.richiedi_pickup_multiplo(
            spedizioni=[
                {
                    "shipment_tracking_number": s["shipment_tracking_number"],
                    "product_code": s["product_code"],
                    "pesi_scatoloni_kg": s["pesi_scatoloni_kg"],
                }
                for s in spedizioni
            ],
            data_pickup_iso=data_iso,
        )
    except (dhl.DHLConfigError, dhl.DHLAPIError) as exc:
        status = 502 if isinstance(exc, dhl.DHLAPIError) else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    aggiornate = db.registra_pickup_multiplo(
        body.spedizione_ids, dispatch_confirmation_number=risposta["dispatchConfirmationNumbers"][0],
    )
    return [SpedizioneResponse(**a) for a in aggiornate]


@router.delete("/spedizioni/{spedizione_id}", status_code=204)
def elimina_bozza_spedizione(spedizione_id: str) -> None:
    """Cancella SOLO se ancora in stato 'bozza' — nessuna chiamata DHL con
    effetto reale è mai avvenuta per una bozza, quindi non c'è nulla da
    annullare lato DHL."""
    if not db.elimina_spedizione_bozza(spedizione_id):
        raise HTTPException(status_code=404, detail=f"Spedizione {spedizione_id} non trovata o non in stato 'bozza'")

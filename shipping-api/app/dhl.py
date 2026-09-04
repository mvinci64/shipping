"""Client MyDHL API (DHL Express) — Basic Auth, ambiente di produzione.

Implementa solo la chiamata di "validazione" (POST /rates): quota una
spedizione — verifica indirizzi, servizi disponibili, prezzo stimato — senza
creare nulla lato DHL e senza emettere etichetta. Emula lo stato "bozza"
richiesto dal dominio, dato che MyDHL API non ha un vero draft nativo (a
differenza di BRT). La creazione reale (POST /shipments, con emissione
etichetta) è la conferma vera e propria — non ancora implementata: la
aggiungiamo solo quando la FSM bozza→confermata→ritirata esiste, per non
rischiare di emettere spedizioni reali da un endpoint di prova.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

# DHL_API_BASE_URL sovrascrive l'URL — utile finché l'app è in sandbox
# (approvazione produzione "pending"): il default resta l'host di
# produzione, ma va puntato all'ambiente test finché l'account non è
# attivo, per non rischiare di usare per sbaglio le chiavi sbagliate
# sull'host sbagliato.
BASE_URL = os.environ.get("DHL_API_BASE_URL", "https://express.api.dhl.com/mydhlapi")

ORIGIN_COUNTRY_CODE = os.environ.get("DHL_ORIGIN_COUNTRY_CODE", "IT")
ORIGIN_POSTAL_CODE = os.environ.get("DHL_ORIGIN_POSTAL_CODE", "")
ORIGIN_CITY = os.environ.get("DHL_ORIGIN_CITY", "")
ORIGIN_ADDRESS_LINE = os.environ.get("DHL_ORIGIN_ADDRESS_LINE", "")

# Dati di contatto mittente — richiesti solo da POST /shipments (createShipment),
# non da /rates. Presi dallo screenshot del portale MyDHL+ (27/08/2026).
ORIGIN_COMPANY_NAME = os.environ.get("DHL_ORIGIN_COMPANY_NAME", "")
ORIGIN_CONTACT_NAME = os.environ.get("DHL_ORIGIN_CONTACT_NAME", "")
ORIGIN_EMAIL = os.environ.get("DHL_ORIGIN_EMAIL", "")
ORIGIN_PHONE = os.environ.get("DHL_ORIGIN_PHONE", "")

# Dimensioni scatolone in cm — se non censite, il pacco viene quotato a solo
# peso (meno preciso: DHL applica comunque il peso volumetrico se lo scarto
# rispetto al peso reale è troppo alto, ma senza dimensioni non lo sappiamo
# in anticipo).
SCATOLONE_DIM_CM = {
    "lunghezza": os.environ.get("DHL_SCATOLONE_LUNGHEZZA_CM"),
    "larghezza": os.environ.get("DHL_SCATOLONE_LARGHEZZA_CM"),
    "altezza": os.environ.get("DHL_SCATOLONE_ALTEZZA_CM"),
}


class DHLConfigError(RuntimeError):
    """Manca una variabile d'ambiente necessaria per chiamare MyDHL API."""


class DHLAPIError(RuntimeError):
    """MyDHL API ha risposto con un errore (4xx/5xx)."""

    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"MyDHL API {status_code}: {payload}")


def _credentials() -> tuple[str, str, str]:
    account = os.environ.get("DHL_ACCOUNT_NUMBER")
    username = os.environ.get("DHL_API_USERNAME")
    password = os.environ.get("DHL_API_PASSWORD")
    if not (account and username and password):
        raise DHLConfigError(
            "DHL_ACCOUNT_NUMBER / DHL_API_USERNAME / DHL_API_PASSWORD non impostate (vedi .env.example)"
        )
    return account, username, password


def _package(peso_kg: float) -> dict:
    package = {"weight": peso_kg}
    if all(SCATOLONE_DIM_CM.values()):
        package["dimensions"] = {
            "length": float(SCATOLONE_DIM_CM["lunghezza"]),
            "width": float(SCATOLONE_DIM_CM["larghezza"]),
            "height": float(SCATOLONE_DIM_CM["altezza"]),
        }
    return package


def valida_spedizione(
    *,
    destinatario_cap: str,
    destinatario_citta: str,
    destinatario_provincia: str,
    destinatario_paese: str,
    pesi_scatoloni_kg: list[float],
    data_spedizione_iso: str,
) -> dict:
    """Chiama POST /rates per validare/quotare la spedizione.

    destinatario_paese va passato come codice ISO2 (es. "IT"); il DB del
    Portal ha invece il nome esteso ("Italia") in customers.country — la
    conversione è a carico del chiamante (vedi routers/spedizioni.py).
    """
    account, username, password = _credentials()
    if not (ORIGIN_POSTAL_CODE and ORIGIN_CITY and ORIGIN_ADDRESS_LINE):
        raise DHLConfigError(
            "Indirizzo di origine (magazzino VISCOTTA) non configurato: "
            "DHL_ORIGIN_POSTAL_CODE / DHL_ORIGIN_CITY / DHL_ORIGIN_ADDRESS_LINE"
        )

    payload = {
        "customerDetails": {
            "shipperDetails": {
                "postalCode": ORIGIN_POSTAL_CODE,
                "cityName": ORIGIN_CITY,
                "countryCode": ORIGIN_COUNTRY_CODE,
                "addressLine1": ORIGIN_ADDRESS_LINE,
            },
            "receiverDetails": {
                "postalCode": destinatario_cap,
                "cityName": destinatario_citta,
                "provinceCode": destinatario_provincia,
                "countryCode": destinatario_paese,
            },
        },
        "accounts": [{"typeCode": "shipper", "number": account}],
        "plannedShippingDateAndTime": f"{data_spedizione_iso}T09:00:00GMT+02:00",
        "unitOfMeasurement": "metric",
        "isCustomsDeclarable": destinatario_paese != ORIGIN_COUNTRY_CODE,
        "packages": [_package(peso) for peso in pesi_scatoloni_kg],
    }

    response = requests.post(
        f"{BASE_URL}/rates",
        json=payload,
        auth=(username, password),
        timeout=20,
    )
    if response.status_code >= 400:
        raise DHLAPIError(response.status_code, _safe_json(response))
    return response.json()


CONTRASSEGNO_SERVICE_CODE = "KB"

# Metodo di incasso del contrassegno — specifica DHL (04/09/2026):
# G: Ass. Circolare intestato al mittente
# L: Ass. Circolare intestato alla casa mandante
# Q: Ass. Ban. o Post. intestato al mittente
# R: Ass. Ban. o Post. intestato alla casa mandante
# Y: Cash, POS
# K: Cash, POS o Assegno (Banc./Post./Circolare) intestato mittente
# J: Cash, POS o Assegno (Banc./Post./Circolare) intestato casa mandante
CONTRASSEGNO_METODI_VALIDI = {"G", "L", "Q", "R", "Y", "K", "J"}


def crea_spedizione(
    *,
    order_number: str,
    product_code: str,
    destinatario_nome: str,
    destinatario_email: str,
    destinatario_telefono: str,
    destinatario_indirizzo: str,
    destinatario_cap: str,
    destinatario_citta: str,
    destinatario_provincia: str,
    destinatario_paese: str,
    pesi_scatoloni_kg: list[float],
    data_spedizione_iso: str,
    contrassegno_eur: float | None = None,
    contrassegno_metodo: str = "Q",
) -> dict:
    """Chiama POST /shipments — crea la spedizione reale ed emette
    l'etichetta (base64 in risposta). A differenza di valida_spedizione
    (/rates), QUESTA CHIAMATA HA EFFETTO: in produzione genera una
    spedizione DHL vera con relativo costo. Va sempre preceduta da una
    valida_spedizione per scegliere product_code, e va agganciata alla FSM
    bozza→confermata (non esposta come endpoint diretto finché la FSM non
    esiste — vedi piano-sprint.md Sprint 2).

    contrassegno_eur: se valorizzato, aggiunge il servizio contrassegno
    (special service serviceCode "KB", specifica DHL 04/09/2026) — importo
    riscosso alla consegna. contrassegno_metodo è una delle lettere in
    CONTRASSEGNO_METODI_VALIDI; il payload MyDHL vuole la lettera ripetuta
    3 volte (es. "Q" -> "QQQ", non ancora chiaro perché, così da specifica).
    """
    account, username, password = _credentials()
    if not (ORIGIN_POSTAL_CODE and ORIGIN_CITY and ORIGIN_ADDRESS_LINE):
        raise DHLConfigError(
            "Indirizzo di origine (magazzino VISCOTTA) non configurato: "
            "DHL_ORIGIN_POSTAL_CODE / DHL_ORIGIN_CITY / DHL_ORIGIN_ADDRESS_LINE"
        )
    if not (ORIGIN_COMPANY_NAME and ORIGIN_CONTACT_NAME and ORIGIN_EMAIL and ORIGIN_PHONE):
        raise DHLConfigError(
            "Dati di contatto mittente non configurati: "
            "DHL_ORIGIN_COMPANY_NAME / DHL_ORIGIN_CONTACT_NAME / DHL_ORIGIN_EMAIL / DHL_ORIGIN_PHONE"
        )
    if contrassegno_eur is not None and contrassegno_metodo not in CONTRASSEGNO_METODI_VALIDI:
        raise DHLConfigError(
            f"contrassegno_metodo {contrassegno_metodo!r} non valido — atteso uno tra {sorted(CONTRASSEGNO_METODI_VALIDI)}"
        )

    payload = {
        "plannedShippingDateAndTime": f"{data_spedizione_iso}T09:00:00GMT+02:00",
        "pickup": {"isRequested": False},
        "productCode": product_code,
        "accounts": [{"typeCode": "shipper", "number": account}],
        "outputImageProperties": {
            "printerDPI": 300,
            "encodingFormat": "pdf",
            "imageOptions": [{"typeCode": "label", "templateName": "ECOM26_84_001"}],
        },
        "customerDetails": {
            "shipperDetails": {
                "postalAddress": {
                    "postalCode": ORIGIN_POSTAL_CODE,
                    "cityName": ORIGIN_CITY,
                    "countryCode": ORIGIN_COUNTRY_CODE,
                    "addressLine1": ORIGIN_ADDRESS_LINE,
                },
                "contactInformation": {
                    "companyName": ORIGIN_COMPANY_NAME,
                    "fullName": ORIGIN_CONTACT_NAME,
                    "email": ORIGIN_EMAIL,
                    "phone": ORIGIN_PHONE,
                },
            },
            "receiverDetails": {
                "postalAddress": {
                    "postalCode": destinatario_cap,
                    "cityName": destinatario_citta,
                    "provinceCode": destinatario_provincia,
                    "countryCode": destinatario_paese,
                    "addressLine1": destinatario_indirizzo,
                },
                "contactInformation": {
                    "companyName": destinatario_nome,
                    "fullName": destinatario_nome,
                    "email": destinatario_email,
                    "phone": destinatario_telefono,
                },
            },
        },
        "content": {
            "packages": [
                {**_package(peso), "customerReferences": [{"value": order_number, "typeCode": "CU"}]}
                for peso in pesi_scatoloni_kg
            ],
            "isCustomsDeclarable": destinatario_paese != ORIGIN_COUNTRY_CODE,
            "declaredValue": 1,
            "declaredValueCurrency": "EUR",
            "description": "Prodotti da forno artigianali",
            "incoterm": "DAP",
            "unitOfMeasurement": "metric",
        },
    }

    if contrassegno_eur is not None:
        # NON dentro "content": MyDHL API lo rifiuta lì (422 "extraneous
        # key [valueAddedServices] is not permitted", verificato in
        # produzione il 04/09/2026) — va a livello radice del payload.
        payload["valueAddedServices"] = [{
            "serviceCode": CONTRASSEGNO_SERVICE_CODE,
            "value": contrassegno_eur,
            "currency": "EUR",
            "method": contrassegno_metodo * 3,
        }]

    response = requests.post(
        f"{BASE_URL}/shipments",
        json=payload,
        auth=(username, password),
        timeout=30,
    )
    if response.status_code >= 400:
        raise DHLAPIError(response.status_code, _safe_json(response))
    return response.json()


def richiedi_pickup(
    *,
    shipment_tracking_number: str,
    product_code: str,
    pesi_scatoloni_kg: list[float],
    data_pickup_iso: str,
    ora_inizio: str = "13:00",
    ora_fine: str = "17:00",
) -> dict:
    """Chiama POST /pickups — prenota il ritiro per una spedizione già
    creata (shipment_tracking_number da crea_spedizione). HA EFFETTO REALE
    come crea_spedizione: stessa cautela, non esposta come endpoint finché
    non c'è la FSM bozza→confermata."""
    account, username, password = _credentials()
    if not (ORIGIN_POSTAL_CODE and ORIGIN_CITY and ORIGIN_ADDRESS_LINE):
        raise DHLConfigError(
            "Indirizzo di origine (magazzino VISCOTTA) non configurato: "
            "DHL_ORIGIN_POSTAL_CODE / DHL_ORIGIN_CITY / DHL_ORIGIN_ADDRESS_LINE"
        )
    if not (ORIGIN_COMPANY_NAME and ORIGIN_CONTACT_NAME and ORIGIN_EMAIL and ORIGIN_PHONE):
        raise DHLConfigError(
            "Dati di contatto mittente non configurati: "
            "DHL_ORIGIN_COMPANY_NAME / DHL_ORIGIN_CONTACT_NAME / DHL_ORIGIN_EMAIL / DHL_ORIGIN_PHONE"
        )

    payload = {
        "plannedPickupDateAndTime": f"{data_pickup_iso}T{ora_inizio}:00GMT+02:00",
        "closeTime": ora_fine,
        "location": "reception",
        "locationType": "business",
        "accounts": [{"typeCode": "shipper", "number": account}],
        "shipmentDetails": [
            {
                "shipmentTrackingNumber": shipment_tracking_number,
                "productCode": product_code,
                "unitOfMeasurement": "metric",
                "packages": [_package(peso) for peso in pesi_scatoloni_kg],
            }
        ],
        "customerDetails": {
            "shipperDetails": {
                "postalAddress": {
                    "postalCode": ORIGIN_POSTAL_CODE,
                    "cityName": ORIGIN_CITY,
                    "countryCode": ORIGIN_COUNTRY_CODE,
                    "addressLine1": ORIGIN_ADDRESS_LINE,
                },
                "contactInformation": {
                    "companyName": ORIGIN_COMPANY_NAME,
                    "fullName": ORIGIN_CONTACT_NAME,
                    "email": ORIGIN_EMAIL,
                    "phone": ORIGIN_PHONE,
                },
            },
        },
    }

    response = requests.post(
        f"{BASE_URL}/pickups",
        json=payload,
        auth=(username, password),
        timeout=30,
    )
    if response.status_code >= 400:
        raise DHLAPIError(response.status_code, _safe_json(response))
    return response.json()


def cancella_pickup(
    *,
    dispatch_confirmation_number: str,
    requestor_name: str,
    reason: str,
) -> None:
    """Chiama DELETE /pickups/{dispatchConfirmationNumber} — annulla un
    ritiro già prenotato (dispatch_confirmation_number da richiedi_pickup,
    es. "PRG260907035858"). Specifica DHL (04/09/2026): stesso endpoint
    dell'ambiente di test, ma senza il segmento "/test/" (già assente da
    BASE_URL in produzione). HA EFFETTO REALE come richiedi_pickup: stessa
    cautela. NON annulla la spedizione stessa (l'AWB) — solo il ritiro."""
    _, username, password = _credentials()
    response = requests.delete(
        f"{BASE_URL}/pickups/{dispatch_confirmation_number}",
        params={"requestorName": requestor_name, "reason": reason},
        auth=(username, password),
        timeout=30,
    )
    if response.status_code >= 400:
        raise DHLAPIError(response.status_code, _safe_json(response))


def _safe_json(response: requests.Response):
    try:
        return response.json()
    except ValueError:
        return response.text

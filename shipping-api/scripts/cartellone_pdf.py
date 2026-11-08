"""Cartellone spedizioni in PDF, un foglio A4 per gruppo di uscita.

Serve quando i gruppi arrivano come NOTA da miniMRP: invece di aprire la
pagina web e incollare gli ordini nel form, si passa la nota qui e si
ottiene il PDF già pronto da stampare.

Uso (dalla cartella shipping-api, con la venv attiva e DATABASE_URL in .env):

    # gruppi espliciti, uno per opzione: "etichetta=ordini separati da virgola"
    python scripts/cartellone_pdf.py -o /tmp/cartellone.pdf \
        -g "lun 09-11=ORD-20260505-5931, IMPORT-DMLAB-20261020-01" \
        -g "mar 10-11=ORD-20261016-3553, ORD-20260525-5006"

    # oppure incollando la nota di miniMRP (anche la tabella intera):
    python scripts/cartellone_pdf.py -o /tmp/cartellone.pdf < nota.txt

Nel formato nota: ogni riga che contiene un numero d'ordine vale per quel
solo ordine (il resto della riga — cliente, città, quantità — viene
ignorato, così la tabella di miniMRP si incolla senza ripulirla); ogni riga
SENZA numero d'ordine apre un gruppo nuovo e ne diventa il titolo. I gruppi
che restano vuoti (le note di coda) vengono scartati.

Sola lettura sul DB: nessuna scrittura, nessuna chiamata al corriere.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db
from app.cartellone import make_cartellone_pdf

# ORD-20261102-5007, IMPORT-DMLAB-20261020-01: maiuscole/trattini, almeno
# un blocco di cifre. Abbastanza larga da prendere i prefissi di import
# senza catturare le città o le date della nota (07-11, 2026-11-08).
TOKEN_ORDINE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{4,}(?:-\d+)?\b")


def ordini_di_riga(riga: str) -> list[str]:
    return TOKEN_ORDINE.findall(riga)


def parse_nota(testo: str) -> list[dict]:
    """Nota → [{"etichetta", "ordini"}], nell'ordine di lettura."""
    gruppi: list[dict] = []
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga:
            continue
        trovati = ordini_di_riga(riga)
        if trovati:
            if not gruppi:
                gruppi.append({"etichetta": "Gruppo 1", "ordini": []})
            gruppi[-1]["ordini"].extend(trovati)
        else:
            gruppi.append({"etichetta": riga.lstrip("#").strip().rstrip(":"), "ordini": []})
    return [g for g in gruppi if g["ordini"]]


def parse_opzioni(valori: list[str]) -> list[dict]:
    """-g "etichetta=ORD-1, ORD-2" → [{"etichetta", "ordini"}]."""
    gruppi = []
    for i, valore in enumerate(valori, start=1):
        etichetta, _, elenco = valore.partition("=")
        if not elenco:
            etichetta, elenco = f"Gruppo {i}", valore
        ordini = [n for n in re.split(r"[\s,;]+", elenco) if n]
        if not ordini:
            sys.exit(f"gruppo senza ordini: {valore!r}")
        gruppi.append({"etichetta": etichetta.strip(), "ordini": ordini})
    return gruppi


def risolvi(gruppi: list[dict]) -> list[dict]:
    """Aggiunge a ogni gruppo le righe lette dal DB e i numeri non trovati.
    Non applica il filtro "in prenotazione": gli ordini che non lo passano
    arrivano con in_prenotazione=False e sul foglio sono segnalati (vedi
    db.fetch_elenco_per_ordini)."""
    risolti = []
    for gruppo in gruppi:
        ordini_db = db.fetch_elenco_per_ordini(gruppo["ordini"])
        trovati = {o["order_number"] for o in ordini_db}
        risolti.append({
            "etichetta": gruppo["etichetta"],
            "righe": [
                {
                    "order_number": o["order_number"],
                    "cliente": o["cliente"],
                    "data_consegna": o["data_consegna"],
                    "in_prenotazione": o["in_prenotazione"],
                }
                for o in ordini_db
            ],
            "mancanti": [n for n in gruppo["ordini"] if n not in trovati],
        })
    return risolti


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", required=True, help="file PDF da scrivere")
    ap.add_argument("-g", "--gruppo", action="append", default=[],
                    help='"etichetta=ORD-1, ORD-2" — ripetibile, un foglio per opzione')
    ap.add_argument("nota", nargs="?", type=argparse.FileType(encoding="utf-8"), default=None,
                    help="file con la nota di miniMRP (default: stdin, se non si usa -g)")
    args = ap.parse_args()

    if args.gruppo:
        gruppi = parse_opzioni(args.gruppo)
    else:
        sorgente = args.nota or sys.stdin
        gruppi = parse_nota(sorgente.read())
    if not gruppi:
        sys.exit("nessun gruppo con ordini: usa -g oppure passa la nota di miniMRP")

    risolti = risolvi(gruppi)
    Path(args.output).write_bytes(make_cartellone_pdf(risolti))

    for g in risolti:
        invii = len({r["cliente"] for r in g["righe"]})
        print(f"{g['etichetta']}: {invii} invii · {len(g['righe'])} ordini", end="")
        segnalati = [r["order_number"] for r in g["righe"] if not r["in_prenotazione"]]
        if segnalati:
            print(f" · NON in prenotazione: {', '.join(segnalati)}", end="")
        if g["mancanti"]:
            print(f" · NON TROVATI: {', '.join(g['mancanti'])}", end="")
        print()
    print(f"Scritto {args.output}")


if __name__ == "__main__":
    main()

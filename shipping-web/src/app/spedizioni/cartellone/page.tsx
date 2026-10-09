import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";
import { StampaAutomatica } from "./StampaAutomatica";

export const metadata = { title: "Cartellone spedizioni — VISCOTTA" };

type Riga = { order_number: string; cliente: string; data_consegna: string | null };

// Tutta l'aritmetica sui giorni lavorativi lavora in UTC (parse e
// serializzazione), per non sfasare di un giorno nei fusi avanti su UTC
// (es. CEST, +2h: new Date(iso+"T00:00:00") locale + .toISOString() UTC
// mischiati facevano tornare indietro di un giorno in più del previsto).
function isoDataUTC(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function parseISOUTC(iso: string): Date {
  return new Date(iso + "T00:00:00Z");
}

// Data di oggi nel calendario locale (non UTC: "oggi" è un concetto locale),
// come stringa ISO da usare poi solo con l'aritmetica UTC qui sopra.
function oggiISO(): string {
  const oggi = new Date();
  const y = oggi.getFullYear();
  const m = String(oggi.getMonth() + 1).padStart(2, "0");
  const d = String(oggi.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function spostaGiorniLavorativi(iso: string, n: number): string {
  const passo = n >= 0 ? 1 : -1;
  const d = parseISOUTC(iso);
  let mossi = 0;
  while (mossi < Math.abs(n)) {
    d.setUTCDate(d.getUTCDate() + passo);
    const giornoSettimana = d.getUTCDay();
    if (giornoSettimana !== 0 && giornoSettimana !== 6) mossi++;
  }
  return isoDataUTC(d);
}

// I due giorni lavorativi successivi a oggi, saltando sabato e domenica —
// default del cartellone quando non si passano date esplicite.
function prossimiDueGiorniLavorativi(): [string, string] {
  const giorno1 = spostaGiorniLavorativi(oggiISO(), 1);
  const giorno2 = spostaGiorniLavorativi(giorno1, 1);
  return [giorno1, giorno2];
}

// Il reparto spedisce con 2 giorni lavorativi di anticipo sulla consegna
// richiesta dal cliente (tempo di transito corriere) — non esiste una
// colonna "data di spedizione" separata in viscotta.orders, va derivata.
const GIORNI_LAVORATIVI_ANTICIPO = 2;

function dataPartenza(dataConsegna: string): string {
  return spostaGiorniLavorativi(dataConsegna, -GIORNI_LAVORATIVI_ANTICIPO);
}

function formattaIntestazione(iso: string): { data: string; giorno: string } {
  const d = new Date(iso + "T00:00:00");
  return {
    data: d.toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit" }),
    giorno: d.toLocaleDateString("it-IT", { weekday: "long" }),
  };
}

function formattaDataBreve(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit" });
}

function Zona({ titolo, data, righe }: { titolo: string; data: string; righe: Riga[] }) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="mb-3 flex items-baseline gap-4 border-2 border-zinc-900 bg-amber-100 px-4 py-1.5 dark:border-zinc-100 dark:bg-amber-950">
        <span className="font-mono text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-amber-200">
          {titolo}
        </span>
        <span className="text-sm font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
          {data} — in partenza
        </span>
        <span className="ml-auto font-mono text-sm text-zinc-600 dark:text-zinc-400">
          {righe.length} {righe.length === 1 ? "ordine" : "ordini"}
        </span>
      </div>
      <div className="flex-1 border-t-2 border-zinc-900 dark:border-zinc-100">
        {righe.length === 0 ? (
          <div className="flex items-center justify-center border-b-2 border-zinc-900 py-6 text-sm italic text-zinc-500 dark:border-zinc-100 dark:text-zinc-400">
            — nessun ordine in partenza questo giorno —
          </div>
        ) : (
          righe.map((r, i) => (
            <div
              key={r.order_number}
              className="flex items-center gap-4 border-b border-zinc-400 py-2 dark:border-zinc-700"
            >
              <div className="h-5 w-5 flex-none border-2 border-zinc-900 dark:border-zinc-100" />
              <div className="w-6 flex-none text-right font-mono text-sm text-zinc-500">{i + 1}</div>
              <div className="flex-1 text-xl font-semibold text-zinc-900 dark:text-zinc-50">{r.cliente}</div>
              <div className="flex-none text-right font-mono text-xs text-zinc-500">
                <div>{r.order_number}</div>
                <div>consegna {r.data_consegna ? formattaDataBreve(r.data_consegna) : "—"}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default async function Cartellone({
  searchParams,
}: {
  searchParams: Promise<{ giorno1?: string; giorno2?: string }>;
}) {
  const params = await searchParams;
  const defaultGiorni = prossimiDueGiorniLavorativi();
  const giorno1 = params.giorno1 || defaultGiorni[0];
  const giorno2 = params.giorno2 || defaultGiorni[1];

  // /spedizioni/elenco filtra per data di CONSEGNA, non di partenza — la
  // finestra va spostata avanti di GIORNI_LAVORATIVI_ANTICIPO per prendere
  // gli ordini la cui consegna richiesta cade quel tanto dopo i due giorni
  // di partenza mostrati nel cartellone.
  const consegnaPerGiorno1 = spostaGiorniLavorativi(giorno1, GIORNI_LAVORATIVI_ANTICIPO);
  const consegnaPerGiorno2 = spostaGiorniLavorativi(giorno2, GIORNI_LAVORATIVI_ANTICIPO);
  const [dataDa, dataA] = [consegnaPerGiorno1, consegnaPerGiorno2].sort();

  const { data: righeTutte, error } = await shippingClient
    .GET("/spedizioni/elenco", { params: { query: { data_da: dataDa, data_a: dataA } } })
    .catch((cause) => ({
      data: undefined,
      error: { detail: cause instanceof Error ? cause.message : String(cause) },
    }));

  const righe = righeTutte?.filter((r) => r.data_consegna !== null);
  const righeGiorno1 = (righe ?? []).filter((r) => dataPartenza(r.data_consegna!) === giorno1);
  const righeGiorno2 = (righe ?? []).filter((r) => dataPartenza(r.data_consegna!) === giorno2);
  const int1 = formattaIntestazione(giorno1);
  const int2 = formattaIntestazione(giorno2);

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans print:bg-white dark:bg-black">
      <div className="flex w-full max-w-4xl flex-col gap-4 px-8 py-8 print:hidden">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold tracking-tight text-black dark:text-zinc-50">Cartellone spedizioni</h1>
          <Link href="/spedizioni" className="text-sm text-zinc-500 hover:underline dark:text-zinc-400">
            ← Ordini da spedire
          </Link>
        </div>
        <form className="flex flex-wrap items-end gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <label className="flex flex-col gap-1 text-sm text-zinc-700 dark:text-zinc-300">
            1° giorno in partenza
            <input
              type="date"
              name="giorno1"
              defaultValue={giorno1}
              className="rounded border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-zinc-700 dark:text-zinc-300">
            2° giorno in partenza
            <input
              type="date"
              name="giorno2"
              defaultValue={giorno2}
              className="rounded border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </label>
          <button
            type="submit"
            className="rounded bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Genera
          </button>
          <StampaAutomatica />
        </form>
        {!righe && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            Impossibile leggere l&apos;elenco (
            {typeof error?.detail === "string" ? error.detail : "errore sconosciuto"}).
          </div>
        )}
      </div>

      <div className="w-full max-w-[210mm] flex-1 border-2 border-zinc-900 bg-white p-8 print:w-auto print:flex-none print:border-0 print:p-0 dark:border-zinc-100 dark:bg-zinc-950 print:dark:bg-white">
        <div className="flex h-full flex-col gap-8 print:h-auto">
          <div className="flex items-baseline justify-between border-b-[3px] border-zinc-900 pb-4 dark:border-zinc-100 print:border-zinc-900">
            <h2 className="font-mono text-2xl font-extrabold uppercase tracking-tight text-zinc-900 print:text-zinc-900 dark:text-zinc-50">
              Spedizioni della settimana
            </h2>
            <span className="font-mono text-sm text-zinc-500">
              {int1.data}–{int2.data} 2026
            </span>
          </div>
          <Zona titolo={int1.data} data={int1.giorno} righe={righeGiorno1} />
          <Zona titolo={int2.data} data={int2.giorno} righe={righeGiorno2} />
          <div className="flex justify-between border-t-2 border-zinc-900 pt-2 font-mono text-[11px] text-zinc-500 dark:border-zinc-100">
            <span>reparto logistica · VISCOTTA</span>
            <span>dati: ordini &quot;in prenotazione&quot;, partenza = consegna richiesta − 2 giorni lavorativi</span>
          </div>
        </div>
      </div>

      <style>{`
        @media print {
          @page { size: A4; margin: 10mm; }
          html, body { background: #fff; }
        }
      `}</style>
    </div>
  );
}

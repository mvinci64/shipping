import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";
import { TabellaSpedizioni } from "./TabellaSpedizioni";

export const metadata = { title: "Spedizioni — VISCOTTA" };

// Sola lettura tranne la selezione multipla per il ritiro unico (vedi
// TabellaSpedizioni) — le altre azioni (conferma spedizione, pickup
// singolo, ...) restano sulla pagina di dettaglio dell'ordine.

export default async function Spedizioni({
  searchParams,
}: {
  searchParams: Promise<{ data_da?: string; data_a?: string }>;
}) {
  const { data_da, data_a } = await searchParams;
  const query: Record<string, string> = {};
  if (data_da) query.data_da = data_da;
  if (data_a) query.data_a = data_a;

  const { data: righe, error } = await shippingClient
    .GET("/spedizioni/elenco", { params: { query } })
    .catch((cause) => ({
      data: undefined,
      error: { detail: cause instanceof Error ? cause.message : String(cause) },
    }));

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-1 flex-col gap-6 px-8 py-16">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
              Ordini da spedire
            </h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Prossime due settimane, salvo filtro esplicito. Nessuna azione da questa vista — clicca un ordine per il
              dettaglio.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/spedizioni/tracking" className="text-sm text-zinc-500 hover:underline dark:text-zinc-400">
              Tracking
            </Link>
            <form action="/logout" method="POST">
              <button type="submit" className="text-sm text-zinc-500 hover:underline dark:text-zinc-400">
                Esci
              </button>
            </form>
          </div>
        </div>

        <form className="flex flex-wrap items-end gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <label className="flex flex-col gap-1 text-sm text-zinc-700 dark:text-zinc-300">
            Consegna dal
            <input
              type="date"
              name="data_da"
              defaultValue={data_da}
              className="rounded border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-zinc-700 dark:text-zinc-300">
            al
            <input
              type="date"
              name="data_a"
              defaultValue={data_a}
              className="rounded border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </label>
          <button
            type="submit"
            className="rounded bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Filtra
          </button>
          {(data_da || data_a) && (
            <Link
              href="/spedizioni"
              className="rounded px-3 py-1.5 text-sm text-zinc-600 hover:underline dark:text-zinc-400"
            >
              Reimposta
            </Link>
          )}
        </form>

        {!righe ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            Impossibile leggere l&apos;elenco (
            {typeof error?.detail === "string" ? error.detail : "errore sconosciuto"}) — verifica che
            shipping-api sia raggiungibile.
          </div>
        ) : righe.length === 0 ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-4 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            Nessun ordine &quot;in prenotazione&quot; nel periodo selezionato.
          </div>
        ) : (
          <TabellaSpedizioni righe={righe} dataDa={data_da} dataA={data_a} />
        )}
      </main>
    </div>
  );
}

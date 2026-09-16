import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";

export const metadata = { title: "Tracking spedizioni — VISCOTTA" };

function formattaData(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("it-IT", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

function formattaDataConsegna(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}

export default async function TrackingSpedizioni({
  searchParams,
}: {
  searchParams: Promise<{ data_da?: string; data_a?: string }>;
}) {
  const { data_da, data_a } = await searchParams;
  const query: Record<string, string> = {};
  if (data_da) query.data_da = data_da;
  if (data_a) query.data_a = data_a;

  const { data: righe, error } = await shippingClient
    .GET("/spedizioni/tracking", { params: { query } })
    .catch((cause) => ({
      data: undefined,
      error: { detail: cause instanceof Error ? cause.message : String(cause) },
    }));

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-4xl flex-1 flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/spedizioni" className="text-xs text-zinc-500 hover:underline dark:text-zinc-400">
            ← Ordini da spedire
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Tracking spedizioni
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Stato DHL reale (sola lettura) per le spedizioni confermate o ritirate nel periodo.
          </p>
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
              href="/spedizioni/tracking"
              className="rounded px-3 py-1.5 text-sm text-zinc-600 hover:underline dark:text-zinc-400"
            >
              Reimposta
            </Link>
          )}
        </form>

        {!righe ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            Impossibile leggere il tracking (
            {typeof error?.detail === "string" ? error.detail : "errore sconosciuto"}) — verifica che
            shipping-api sia raggiungibile.
          </div>
        ) : righe.length === 0 ? (
          <div className="rounded-lg border border-zinc-200 bg-white p-4 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
            Nessuna spedizione confermata o ritirata nel periodo selezionato.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Consegna</th>
                  <th className="px-4 py-2 font-medium">Ordine</th>
                  <th className="px-4 py-2 font-medium">Cliente</th>
                  <th className="px-4 py-2 font-medium">Tracking</th>
                  <th className="px-4 py-2 font-medium">PRG</th>
                  <th className="px-4 py-2 font-medium">Ultimo stato DHL</th>
                  <th className="px-4 py-2 font-medium">Consegna stimata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {righe.map((riga) => (
                  <tr key={riga.order_number} className="bg-white dark:bg-zinc-950">
                    <td className="whitespace-nowrap px-4 py-2 text-zinc-700 dark:text-zinc-300">
                      {formattaDataConsegna(riga.data_consegna)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-900 dark:text-zinc-100">
                      <Link href={`/spedizioni/${riga.order_number}`} className="hover:underline">
                        {riga.order_number}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{riga.cliente}</td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-700 dark:text-zinc-300">
                      {riga.tracking_url ? (
                        <a href={riga.tracking_url} target="_blank" className="hover:underline">
                          {riga.shipment_tracking_number}
                        </a>
                      ) : (
                        riga.shipment_tracking_number
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                      {riga.dispatch_confirmation_number ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                      {riga.errore ? (
                        <span className="text-red-700 dark:text-red-400" title={riga.errore}>
                          Errore tracking
                        </span>
                      ) : (
                        riga.stato_dhl ?? "—"
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-zinc-700 dark:text-zinc-300">
                      {formattaData(riga.consegna_stimata)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

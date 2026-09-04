import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";

export const metadata = { title: "Spedizioni — VISCOTTA" };

// Sola lettura: nessuna azione (conferma spedizione, pickup, ...) da qui.
// Le azioni restano sulle chiamate dirette a shipping-api finché non si
// decide di costruirle in UI — vedi ../../piano-sprint.md, Sprint 4.
const ETICHETTA_STATO: Record<string, { testo: string; classi: string }> = {
  non_iniziata: { testo: "Da iniziare", classi: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300" },
  bozza: { testo: "Bozza", classi: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300" },
  confermata: { testo: "Confermata", classi: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300" },
  ritirata: { testo: "Ritirata", classi: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300" },
  fallita: { testo: "Fallita", classi: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300" },
};

function formattaData(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("it-IT", {
    weekday: "short", day: "numeric", month: "short",
  });
}

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
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Ordini da spedire
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Prossime due settimane, salvo filtro esplicito. Nessuna azione da questa vista — clicca un ordine per il
            dettaglio.
          </p>
        </div>

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
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Consegna</th>
                  <th className="px-4 py-2 font-medium">Ordine</th>
                  <th className="px-4 py-2 font-medium">Cliente</th>
                  <th className="px-4 py-2 font-medium">Colli</th>
                  <th className="px-4 py-2 font-medium">Spedizione</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {righe.map((riga) => {
                  const badge = ETICHETTA_STATO[riga.spedizione_stato] ?? ETICHETTA_STATO.non_iniziata;
                  const href = `/spedizioni/${riga.order_number}?cliente=${encodeURIComponent(riga.cliente)}`;
                  return (
                    <tr key={riga.order_number} className="bg-white hover:bg-zinc-50 dark:bg-zinc-950 dark:hover:bg-zinc-900">
                      <td className="whitespace-nowrap px-4 py-2 text-zinc-700 dark:text-zinc-300">
                        <Link href={href} className="block">
                          {formattaData(riga.data_consegna)}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-900 dark:text-zinc-100">
                        <Link href={href} className="block">
                          {riga.order_number}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                        <Link href={href} className="block">
                          {riga.cliente}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-zinc-700 dark:text-zinc-300">
                        <Link href={href} className="block">
                          {riga.colli_confermati}/{riga.n_colli}
                          {riga.colli_completo && riga.n_colli > 0 ? " ✓" : ""}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2">
                        <Link href={href} className="block">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.classi}`}>
                            {badge.testo}
                          </span>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";

export default async function Home() {
  const { data, error } = await shippingClient.GET("/health").catch((cause) => ({
    data: undefined,
    error: { message: cause instanceof Error ? cause.message : String(cause) },
  }));

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-xl flex-1 flex-col gap-6 px-8 py-16">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            VISCOTTA — Spedizioni
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Interfaccia operativa di reparto (scaffold).
          </p>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            Connessione a shipping-api
          </h2>
          {data ? (
            <p className="mt-2 text-sm text-emerald-700 dark:text-emerald-400">
              ✓ raggiungibile — stato: {data.status}, DB: {data.db}
            </p>
          ) : (
            <p className="mt-2 text-sm text-red-700 dark:text-red-400">
              ✗ non raggiungibile ({error?.message ?? "errore sconosciuto"}) — verifica
              SHIPPING_API_URL e che shipping-api sia in esecuzione
            </p>
          )}
        </div>

        <Link
          href="/spedizioni"
          className="rounded-lg border border-zinc-200 bg-white p-4 text-sm font-medium text-zinc-900 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:border-zinc-700"
        >
          → Ordini da spedire (sola lettura)
        </Link>
      </main>
    </div>
  );
}

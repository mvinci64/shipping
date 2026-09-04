import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";
import { AzioneForm } from "./AzioneForm";
import { creaBozzaAction, confermaSpedizioneAction, richiediPickupAction } from "./actions";

export const metadata = { title: "Dettaglio spedizione — VISCOTTA" };

export default async function DettaglioSpedizione({
  params, searchParams,
}: {
  params: Promise<{ order_number: string }>;
  searchParams: Promise<{ cliente?: string }>;
}) {
  const { order_number } = await params;
  const { cliente } = await searchParams;

  const [cartonizzazione, colli, spedizione] = await Promise.all([
    shippingClient.GET("/cartonizzazioni/{order_number}", { params: { path: { order_number } } }),
    shippingClient.GET("/cartonizzazioni/{order_number}/colli", { params: { path: { order_number } } }),
    shippingClient.GET("/spedizioni/per-ordine/{order_number}", { params: { path: { order_number } } }),
  ]);

  if (!cartonizzazione.data) {
    return (
      <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
        <main className="flex w-full max-w-2xl flex-1 flex-col gap-4 px-8 py-16">
          <p className="text-sm text-red-700 dark:text-red-400">
            Ordine {order_number} non trovato o non cartonizzabile.
          </p>
        </main>
      </div>
    );
  }

  const stato = spedizione.data?.stato ?? "non_iniziata";
  const collliCompleti = colli.data?.completo ?? false;
  const motivoBloccoConferma = !collliCompleti
    ? `Mancano colli da confermare (${colli.data?.confermati.length ?? 0}/${colli.data?.n_totale ?? 0}) — vedi POST /cartonizzazioni/colli/conferma`
    : undefined;

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-1 flex-col gap-6 px-8 py-16">
        <div>
          <Link href="/spedizioni" className="text-xs text-zinc-500 hover:underline dark:text-zinc-400">
            ← Ordini da spedire
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            {cliente ?? order_number}
          </h1>
          <p className="font-mono text-xs text-zinc-500 dark:text-zinc-400">{order_number}</p>
        </div>

        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Cartonizzazione</h2>
          <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
            {cartonizzazione.data.n_scatoloni} colli, {cartonizzazione.data.peso_totale_kg.toFixed(2)} kg totali
          </p>
          {cartonizzazione.data.non_censiti.length > 0 && (
            <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
              SKU non censiti da sistemare a mano:{" "}
              {cartonizzazione.data.non_censiti.map((n) => `${n.qta}× ${n.sku}`).join(", ")}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            <a
              href={`/spedizioni/${order_number}/etichette-colli`}
              target="_blank"
              className="rounded border border-zinc-300 px-2 py-1 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Stampa etichette colli
            </a>
            <a
              href={`/spedizioni/${order_number}/etichette-scatolone`}
              target="_blank"
              className="rounded border border-zinc-300 px-2 py-1 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Stampa etichette scatolone
            </a>
          </div>
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Colli confermati a fine linea</h2>
          <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
            {colli.data?.confermati.length ?? 0}/{colli.data?.n_totale ?? 0}
            {collliCompleti ? " — completo ✓" : ""}
          </p>
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Spedizione DHL</h2>

          {stato === "non_iniziata" && (
            <div className="mt-3">
              <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
                Nessuna bozza ancora. Creare la bozza quota via DHL /rates — nessun effetto reale.
              </p>
              <AzioneForm
                action={creaBozzaAction.bind(null, order_number)}
                etichetta="Crea bozza"
                classi="bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              />
            </div>
          )}

          {spedizione.data && stato === "bozza" && (
            <div className="mt-3 flex flex-col gap-3">
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Bozza creata — prodotto {spedizione.data.product_code ?? "—"}, prezzo stimato{" "}
                {spedizione.data.prezzo_stimato_eur?.toFixed(2) ?? "—"} €
              </p>
              <AzioneForm
                action={confermaSpedizioneAction.bind(null, spedizione.data.id, order_number)}
                etichetta="Conferma spedizione (effetto reale)"
                classi="bg-red-700 text-white hover:bg-red-800"
                testoDaDigitare={order_number}
                bloccatoPer={motivoBloccoConferma}
              />
            </div>
          )}

          {spedizione.data && stato === "confermata" && (
            <div className="mt-3 flex flex-col gap-3">
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Confermata — tracking {spedizione.data.shipment_tracking_number ?? "—"}
                {spedizione.data.tracking_url && (
                  <>
                    {" "}
                    (
                    <a href={spedizione.data.tracking_url} target="_blank" className="underline">
                      link
                    </a>
                    )
                  </>
                )}
              </p>
              <a
                href={`/spedizioni/${order_number}/etichetta-corriere`}
                target="_blank"
                className="w-fit rounded border border-zinc-300 px-2 py-1 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                Stampa etichetta corriere
              </a>
              <AzioneForm
                action={richiediPickupAction.bind(null, spedizione.data.id, order_number)}
                etichetta="Richiedi pickup (effetto reale)"
                classi="bg-red-700 text-white hover:bg-red-800"
                testoDaDigitare={order_number}
              >
                <label className="flex flex-col gap-1 text-xs text-zinc-600 dark:text-zinc-400">
                  Data pickup (vuoto = domani):
                  <input
                    type="date"
                    name="data_pickup"
                    className="rounded border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                  />
                </label>
              </AzioneForm>
            </div>
          )}

          {spedizione.data && stato === "ritirata" && (
            <div className="mt-3 flex flex-col gap-2">
              <p className="text-sm text-emerald-700 dark:text-emerald-400">
                Ritirata — conferma ritiro {spedizione.data.dispatch_confirmation_number ?? "—"}
              </p>
              <a
                href={`/spedizioni/${order_number}/etichetta-corriere`}
                target="_blank"
                className="w-fit rounded border border-zinc-300 px-2 py-1 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                Stampa etichetta corriere
              </a>
            </div>
          )}

          {spedizione.data && stato === "fallita" && (
            <p className="mt-3 text-sm text-red-700 dark:text-red-400">
              Fallita: {spedizione.data.errore ?? "errore sconosciuto"}. Nessun retry automatico — verificare i dati
              e ricreare la bozza a mano se necessario.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}

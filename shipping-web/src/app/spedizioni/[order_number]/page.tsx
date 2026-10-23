import Link from "next/link";
import { shippingClient } from "@/lib/shipping-client";
import { AzioneForm } from "./AzioneForm";
import {
  creaBozzaAction,
  creaBozzaConsolidataAction,
  confermaSpedizioneAction,
  richiediPickupAction,
  confermaColloAction,
} from "./actions";

export const metadata = { title: "Dettaglio spedizione — VISCOTTA" };

export default async function DettaglioSpedizione({
  params, searchParams,
}: {
  params: Promise<{ order_number: string }>;
  searchParams: Promise<{ cliente?: string; data_da?: string; data_a?: string }>;
}) {
  const { order_number } = await params;
  const { cliente, data_da, data_a } = await searchParams;

  // Il filtro data della lista arriva qui via query string (vedi
  // TabellaSpedizioni) e va rimesso nel link di ritorno, altrimenti
  // "← Ordini da spedire" riporta sempre alla finestra di default invece
  // che a quella su cui si stava lavorando (bug segnalato 16/09/2026).
  const queryLista = new URLSearchParams();
  if (data_da) queryLista.set("data_da", data_da);
  if (data_a) queryLista.set("data_a", data_a);
  const hrefLista = queryLista.size > 0 ? `/spedizioni?${queryLista.toString()}` : "/spedizioni";

  const [cartonizzazione, colli, spedizione, consolidabili] = await Promise.all([
    shippingClient.GET("/cartonizzazioni/{order_number}", { params: { path: { order_number } } }),
    shippingClient.GET("/cartonizzazioni/{order_number}/colli", { params: { path: { order_number } } }),
    shippingClient.GET("/spedizioni/per-ordine/{order_number}", { params: { path: { order_number } } }),
    shippingClient.GET("/spedizioni/consolidabili/{order_number}", { params: { path: { order_number } } }),
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
          <Link href={hrefLista} className="text-xs text-zinc-500 hover:underline dark:text-zinc-400">
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
          {!collliCompleti && colli.data && colli.data.mancanti.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {colli.data.mancanti.map((indice) => (
                <AzioneForm
                  key={indice}
                  action={confermaColloAction.bind(null, order_number, indice)}
                  etichetta={`Conferma collo ${indice}/${colli.data!.n_totale}`}
                  classi="bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                />
              ))}
            </div>
          )}
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Spedizione DHL</h2>

          {/* Spedizione consolidata: va detto a schermo, perché pesi,
              prezzo e contrassegno qui sotto sono di TUTTI gli ordini
              elencati, non solo di quello aperto — e la conferma resta
              bloccata finché anche i loro colli non sono confermati. */}
          {spedizione.data && spedizione.data.ordini_aggregati.length > 0 && (
            <div className="mt-2 rounded border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
              <p className="text-xs font-medium text-amber-900 dark:text-amber-200">
                Spedizione unica per {spedizione.data.ordini_aggregati.length + 1} ordini — pesi, prezzo e
                contrassegno sono complessivi.
              </p>
              <ul className="mt-1 flex flex-col gap-0.5 text-xs text-amber-800 dark:text-amber-300">
                {[spedizione.data.order_number, ...spedizione.data.ordini_aggregati].map((o) => {
                  const eCapofila = o === spedizione.data!.order_number;
                  const eQuestaPagina = o === order_number;
                  return (
                    <li key={o}>
                      {eQuestaPagina ? (
                        <span className="font-mono font-semibold">{o}</span>
                      ) : (
                        <Link href={`/spedizioni/${o}`} className="font-mono underline">
                          {o}
                        </Link>
                      )}
                      {eCapofila && " (capofila)"}
                      {eQuestaPagina && " ← ordine aperto"}
                    </li>
                  );
                })}
              </ul>
              <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">
                La conferma richiede i colli confermati di tutti gli ordini elencati.
              </p>
            </div>
          )}

          {stato === "non_iniziata" && (
            <div className="mt-3 flex flex-col gap-4">
              <div>
                <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
                  Nessuna bozza ancora. Creare la bozza quota via DHL /rates — nessun effetto reale.
                </p>
                <AzioneForm
                  action={creaBozzaAction.bind(null, order_number)}
                  etichetta="Crea bozza"
                  classi="bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                />
              </div>

              {/* Consolidamento: compare solo quando questo cliente ha
                  altri ordini in partenza lo stesso giorno, cioè quando
                  spedirli separatamente significherebbe pagare due
                  etichette e far venire due volte il corriere. */}
              {consolidabili.data && consolidabili.data.length > 0 && (
                <div className="rounded border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
                  <h3 className="text-sm font-medium text-amber-900 dark:text-amber-200">
                    Stesso cliente, stessa partenza
                  </h3>
                  <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">
                    Questo cliente ha altri ordini che partono lo stesso giorno. Unendoli si crea una
                    sola spedizione DHL: una etichetta, un ritiro, un contrassegno complessivo. Ogni
                    collo resta marcato col suo ordine.
                  </p>
                  <AzioneForm
                    action={creaBozzaConsolidataAction.bind(null, order_number)}
                    etichetta="Crea bozza unica"
                    classi="mt-1 bg-amber-700 text-white hover:bg-amber-600 dark:bg-amber-600 dark:hover:bg-amber-500"
                  >
                    <div className="flex flex-col gap-1">
                      {consolidabili.data.map((o) => (
                        <label
                          key={o.order_number}
                          className="flex items-center gap-2 text-xs text-amber-900 dark:text-amber-200"
                        >
                          <input
                            type="checkbox"
                            name="ordine_aggregato"
                            value={o.order_number}
                            defaultChecked
                          />
                          <span className="font-mono">{o.order_number}</span>
                          <span className="text-amber-700 dark:text-amber-400">
                            {o.n_colli} {o.n_colli === 1 ? "collo" : "colli"}
                          </span>
                        </label>
                      ))}
                    </div>
                  </AzioneForm>
                </div>
              )}
            </div>
          )}

          {spedizione.data && stato === "bozza" && (
            <div className="mt-3 flex flex-col gap-3">
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Bozza creata — prodotto {spedizione.data.product_code ?? "—"}, prezzo stimato{" "}
                {spedizione.data.prezzo_stimato_eur?.toFixed(2) ?? "—"} €
              </p>
              {spedizione.data.contrassegno_eur != null && (
                <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  Contrassegno: {spedizione.data.contrassegno_eur.toFixed(2)} € da riscuotere alla consegna
                </p>
              )}
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
                Ritirata — tracking {spedizione.data.shipment_tracking_number ?? "—"}
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
                {" "}— conferma ritiro {spedizione.data.dispatch_confirmation_number ?? "—"}
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
            <div className="mt-3 flex flex-col gap-2">
              <p className="text-sm text-red-700 dark:text-red-400">
                Fallita: {spedizione.data.errore ?? "errore sconosciuto"}. Nessun retry automatico — verificare i
                dati e ricreare la bozza a mano se necessario.
              </p>
              <AzioneForm
                action={creaBozzaAction.bind(null, order_number)}
                etichetta="Ricrea bozza"
                classi="bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              />
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

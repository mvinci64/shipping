"use client";

import { useActionState, useState } from "react";
import Link from "next/link";
import { richiediPickupMultiploAction } from "./actions";

type Riga = {
  order_number: string;
  cliente: string;
  data_consegna: string | null;
  n_colli: number;
  colli_confermati: number;
  colli_completo: boolean;
  spedizione_stato: string;
  spedizione_id: string | null;
};

const ETICHETTA_STATO: Record<string, { testo: string; classi: string }> = {
  non_iniziata: { testo: "Da iniziare", classi: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300" },
  bozza: { testo: "Bozza", classi: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300" },
  confermata: { testo: "Confermata", classi: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300" },
  ritirata: { testo: "Ritirata", classi: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300" },
  fallita: { testo: "Fallita", classi: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300" },
};

function formattaData(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "short" });
}

type Props = { righe: Riga[]; dataDa?: string; dataA?: string };

export function TabellaSpedizioni({ righe, dataDa, dataA }: Props) {
  const [selezionate, setSelezionate] = useState<Set<string>>(new Set());
  const [stato, formAction, inCorso] = useActionState(richiediPickupMultiploAction, { errore: null, successo: null });
  const [digitato, setDigitato] = useState("");

  function toggle(id: string) {
    setSelezionate((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const numeroSelezionate = selezionate.size;
  const confermaAttesa = String(numeroSelezionate);
  const bloccato = numeroSelezionate < 2 || digitato !== confermaAttesa;

  return (
    <form action={formAction}>
      {Array.from(selezionate).map((id) => (
        <input key={id} type="hidden" name="spedizione_id" value={id} />
      ))}

      {numeroSelezionate > 0 && (
        <div className="mb-3 flex flex-wrap items-end gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950">
          <div className="text-sm text-blue-900 dark:text-blue-200">
            {numeroSelezionate} spedizioni selezionate per un ritiro unico (un solo passaggio del corriere).
          </div>
          <label className="flex flex-col gap-1 text-sm text-blue-900 dark:text-blue-200">
            Data ritiro (opzionale, default domani)
            <input
              type="date"
              name="data_pickup"
              className="rounded border border-blue-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-blue-800 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-blue-900 dark:text-blue-200">
            Digita <span className="font-mono font-semibold">{confermaAttesa}</span> per confermare
            (effetto reale, irreversibile):
            <input
              type="text"
              value={digitato}
              onChange={(e) => setDigitato(e.target.value)}
              className="rounded border border-blue-300 bg-white px-2 py-1 font-mono text-sm text-zinc-900 dark:border-blue-800 dark:bg-zinc-900 dark:text-zinc-100"
              autoComplete="off"
            />
          </label>
          <button
            type="submit"
            disabled={bloccato || inCorso}
            className="rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 hover:bg-blue-800"
          >
            {inCorso ? "In corso…" : "Richiedi ritiro unico"}
          </button>
        </div>
      )}
      {stato.errore && (
        <p className="mb-3 text-sm text-red-700 dark:text-red-400" role="alert">{stato.errore}</p>
      )}
      {stato.successo && (
        <p className="mb-3 text-sm text-emerald-700 dark:text-emerald-400">{stato.successo}</p>
      )}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
            <tr>
              <th className="px-4 py-2 font-medium"></th>
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
              // Propaga il filtro data attivo nella lista, così il link
              // "← Ordini da spedire" sulla pagina di dettaglio torna alla
              // stessa finestra invece che a quella di default (bug
              // segnalato dall'utente 16/09/2026).
              const query = new URLSearchParams({ cliente: riga.cliente });
              if (dataDa) query.set("data_da", dataDa);
              if (dataA) query.set("data_a", dataA);
              const href = `/spedizioni/${riga.order_number}?${query.toString()}`;
              const selezionabile = riga.spedizione_stato === "confermata" && riga.spedizione_id;
              return (
                <tr key={riga.order_number} className="bg-white hover:bg-zinc-50 dark:bg-zinc-950 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2">
                    {selezionabile && (
                      <input
                        type="checkbox"
                        checked={selezionate.has(riga.spedizione_id!)}
                        onChange={() => toggle(riga.spedizione_id!)}
                        aria-label={`Seleziona ${riga.order_number} per ritiro unico`}
                      />
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    <Link href={href} className="block">{formattaData(riga.data_consegna)}</Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-zinc-900 dark:text-zinc-100">
                    <Link href={href} className="block">{riga.order_number}</Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                    <Link href={href} className="block">{riga.cliente}</Link>
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
    </form>
  );
}

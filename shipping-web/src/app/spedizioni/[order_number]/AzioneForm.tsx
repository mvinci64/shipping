"use client";

import { useActionState, useState } from "react";
import type { StatoAzione } from "./actions";

type Props = {
  action: (prevState: StatoAzione, formData: FormData) => Promise<StatoAzione>;
  etichetta: string;
  classi: string;
  /** Se presente, richiede che l'operatore digiti esattamente questo testo
   * prima di poter inviare — solo per azioni con effetto reale (costo o
   * ritiro reale), non per la creazione della bozza (nessun effetto). */
  testoDaDigitare?: string;
  children?: React.ReactNode;
  /** Se presente, il form resta bloccato indipendentemente dal testo
   * digitato — con il motivo mostrato all'operatore (es. colli non ancora
   * confermati). Il backend applica comunque lo stesso vincolo (409): è
   * un aiuto per non far provare a vuoto, non l'unico controllo. */
  bloccatoPer?: string;
};

export function AzioneForm({ action, etichetta, classi, testoDaDigitare, children, bloccatoPer }: Props) {
  const [stato, formAction, inCorso] = useActionState<StatoAzione, FormData>(action, { errore: null });
  const [digitato, setDigitato] = useState("");
  const bloccato = Boolean(bloccatoPer) || (testoDaDigitare !== undefined && digitato !== testoDaDigitare);

  return (
    <form action={formAction} className="flex flex-col gap-2">
      {children}
      {testoDaDigitare && (
        <label className="flex flex-col gap-1 text-xs text-zinc-600 dark:text-zinc-400">
          Digita <span className="font-mono font-semibold">{testoDaDigitare}</span> per confermare
          (effetto reale, irreversibile):
          <input
            type="text"
            value={digitato}
            onChange={(e) => setDigitato(e.target.value)}
            className="rounded border border-zinc-300 bg-white px-2 py-1 font-mono text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            autoComplete="off"
          />
        </label>
      )}
      <button
        type="submit"
        disabled={bloccato || inCorso}
        className={`rounded px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${classi}`}
      >
        {inCorso ? "In corso…" : etichetta}
      </button>
      {bloccatoPer && <p className="text-xs text-amber-700 dark:text-amber-400">{bloccatoPer}</p>}
      {stato.errore && (
        <p className="text-xs text-red-700 dark:text-red-400">{stato.errore}</p>
      )}
    </form>
  );
}

"use client";

import { useActionState } from "react";
import { loginAction, type StatoLogin } from "./actions";

const statoIniziale: StatoLogin = { errore: null };

export default function Login() {
  const [stato, formAction, inCorso] = useActionState(loginAction, statoIniziale);

  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <form
        action={formAction}
        className="flex w-full max-w-sm flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-black dark:text-zinc-50">
            VISCOTTA — Spedizioni
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Accesso riservato al reparto.</p>
        </div>

        <label className="flex flex-col gap-1 text-sm text-zinc-700 dark:text-zinc-300">
          Email
          <input
            type="email"
            name="email"
            required
            autoComplete="username"
            className="rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-zinc-700 dark:text-zinc-300">
          Password
          <input
            type="password"
            name="password"
            required
            autoComplete="current-password"
            className="rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </label>

        {stato.errore && (
          <p className="text-sm text-red-700 dark:text-red-400" role="alert">
            {stato.errore}
          </p>
        )}

        <button
          type="submit"
          disabled={inCorso}
          className="rounded bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {inCorso ? "Accesso in corso…" : "Accedi"}
        </button>
      </form>
    </div>
  );
}

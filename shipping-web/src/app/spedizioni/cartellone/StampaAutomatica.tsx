"use client";

import { useEffect } from "react";

// Apre la finestra di stampa da sola all'arrivo sulla pagina — il reparto
// non deve ricordarsi Cmd/Ctrl+P. Il bottone resta per poter ristampare
// senza ricaricare (es. dopo aver cambiato le date dal form).
export function StampaAutomatica() {
  useEffect(() => {
    const id = setTimeout(() => window.print(), 300);
    return () => clearTimeout(id);
  }, []);

  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="rounded bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 print:hidden dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
    >
      Stampa
    </button>
  );
}

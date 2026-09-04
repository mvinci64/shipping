# shipping-web

Interfaccia operativa di reparto per il dominio spedizioni VISCOTTA (Sprint 4). Next.js 16 (App Router), stesso pattern del Portal (vedi `~/CLAUDE.md`) — pagine Server Component, nessuna chiamata a `shipping-api` dal browser.

Consuma `shipping-api` tramite `@viscotta/shipping-client` (dipendenza locale `file:../client-ts`, tipi generati dal contratto OpenAPI — vedi `../client-ts/README.md`).

## Quick start

```bash
cd shipping-api && source venv/bin/activate && uvicorn app.main:app --reload   # in un terminale separato

cp .env.example .env.local   # SHIPPING_API_URL, default http://localhost:8000
npm install
npm run dev
```

Apri [http://localhost:3000](http://localhost:3000): la home mostra lo stato della connessione a `shipping-api` (health check reale, incluso lo stato del DB) — è il primo tassello dello scaffold, prova che il client tipizzato funziona end-to-end prima di costruirci sopra le viste operative.

## Stato

Scaffold (Sprint 4, in corso). Fatto:

- Progetto Next.js con Tailwind, TypeScript strict
- `src/lib/shipping-client.ts` — istanza del client tipizzato, `SHIPPING_API_URL` da env (server-side)
- Home page: verifica di connettività reale

Da fare (vedi `../piano-sprint.md`):

- Vista lista ordini da spedire con stato (bozza/confermata/ritirata)
- Azione di conferma spedizione e stampa etichetta dalla UI
- Autenticazione/permessi coerenti con l'Order Portal

## Nota tecnica: `turbopack.root`

`next.config.ts` fissa `turbopack.root` alla directory padre di questo progetto (non a `shipping-web` stesso), perché `@viscotta/shipping-client` è collegato via symlink (`file:../client-ts`) e Turbopack non risolve moduli fuori dalla propria root — vedi la sezione "Root directory" della [documentazione Turbopack](https://nextjs.org/docs/app/api-reference/config/next-config-js/turbopack#root-directory). `transpilePackages` è necessario per lo stesso motivo: `client-ts` è distribuito come sorgente TS, non pre-compilato.

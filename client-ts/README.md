# client-ts

Client TypeScript tipizzato per `shipping-api`, generato dal contratto OpenAPI di FastAPI. Pensato per essere consumato da `shipping-web` (Sprint 4) e, se utile, dall'Order Portal — stesso pattern già usato dal Portal per i suoi client interni (contratto generato, non scritto a mano).

Non è ancora pubblicato su un registry: finché non esiste un consumatore reale (`shipping-web`), si importa via path relativo o workspace npm locale.

## Come funziona

1. `shipping-api/scripts/export_openapi.py` scrive `openapi.json` leggendo lo schema direttamente dalle route FastAPI (nessuna chiamata DB, nessuna credenziale necessaria — FastAPI costruisce lo schema dalle firme, non esegue gli endpoint).
2. `openapi-typescript` genera `src/schema.ts` (tipi puri, non toccare a mano — rigenerato a ogni `refresh`).
3. `src/client.ts` è un thin wrapper su [`openapi-fetch`](https://openapi-ts.dev/openapi-fetch/): un client HTTP tipizzato, niente codice generato per i metodi (a differenza di generator più pesanti tipo `openapi-generator`) — path, parametri e corpi di richiesta/risposta sono tipati da TypeScript direttamente sullo schema.

## Rigenerare dopo una modifica a shipping-api

```bash
cd client-ts
npm run refresh   # rilancia export_openapi.py + openapi-typescript
```

`openapi.json` e `src/schema.ts` sono committati (non in `.gitignore`): il contratto è visibile in review come qualunque altro file, invece di essere un artefatto invisibile rigenerato solo in CI.

## Uso da un consumatore (es. shipping-web)

```ts
import { creaShippingClient } from "@viscotta/shipping-client";

const client = creaShippingClient("http://localhost:8000");

const { data, error } = await client.GET("/cartonizzazioni/{order_number}", {
  params: { path: { order_number: "ORD-20260910-1234" } },
});

if (error) {
  // error è tipato sullo schema di risposta 4xx/5xx di FastAPI
} else {
  // data.n_scatoloni, data.scatoloni, ... — tipati
}
```

Per gli endpoint POST con body (es. conferma collo):

```ts
await client.POST("/cartonizzazioni/colli/conferma", {
  body: { codice: "ORD-20260910-1234-01" },
});
```

## Perché non prima di shipping-web

Il contratto (`openapi.json`/`schema.ts`) è generato ora perché è l'ultimo punto aperto dello Sprint 3 e non costa nulla tenerlo aggiornato via `npm run refresh` a ogni sprint successivo. Il client (`client.ts`) resta minimale finché non c'è un vero consumatore: nessuna gestione di retry/auth/error-handling applicativo aggiunta preventivamente — quella arriva quando `shipping-web` (o il Portal) la richiede davvero.

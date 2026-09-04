/**
 * Client TS tipizzato per shipping-api — thin wrapper su openapi-fetch,
 * tipi generati da src/schema.ts (vedi README.md per la pipeline di
 * rigenerazione). Un client per baseUrl: shipping-web e il Portal possono
 * puntare ad ambienti diversi (locale, staging, produzione) creandone uno
 * ciascuno.
 *
 * Esempio:
 *   import { creaShippingClient } from "@viscotta/shipping-client";
 *   const client = creaShippingClient("http://localhost:8000");
 *   const { data, error } = await client.GET("/cartonizzazioni/{order_number}", {
 *     params: { path: { order_number: "ORD-20260910-1234" } },
 *   });
 */
import createClient from "openapi-fetch";
import type { paths } from "./schema.js";

export type { paths } from "./schema.js";

export function creaShippingClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}

export type ShippingClient = ReturnType<typeof creaShippingClient>;

import { creaShippingClient } from "@viscotta/shipping-client";

// Le pagine sono Server Component: la chiamata a shipping-api parte dal
// server Next.js, mai dal browser — SHIPPING_API_URL non ha bisogno del
// prefisso NEXT_PUBLIC_ e resta interno alla rete (stesso pattern del
// Portal, che non espone i suoi servizi backend al client).
const SHIPPING_API_URL = process.env.SHIPPING_API_URL ?? "http://localhost:8000";

export const shippingClient = creaShippingClient(SHIPPING_API_URL);

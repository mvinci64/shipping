"use server";

import { revalidatePath } from "next/cache";
import { shippingClient } from "@/lib/shipping-client";

export type StatoAzione = { errore: string | null };

function messaggioErrore(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg).filter(Boolean).join("; ");
  }
  return "Errore sconosciuto";
}

// Nessun effetto reale: solo quotazione (/rates) e salvataggio in stato
// 'bozza' — vedi shipping-api/app/routers/spedizioni.py.
export async function creaBozzaAction(
  orderNumber: string, _prev: StatoAzione, _formData: FormData,
): Promise<StatoAzione> {
  const { error } = await shippingClient.POST("/spedizioni", {
    params: { query: { order_number: orderNumber } },
  });
  if (error) return { errore: messaggioErrore(error) };
  revalidatePath(`/spedizioni/${orderNumber}`);
  return { errore: null };
}

// EFFETTO REALE: crea la spedizione DHL vera con relativo costo. Il gate
// sui colli confermati è lato shipping-api (409 se mancano) — qui si
// propaga solo l'errore.
export async function confermaSpedizioneAction(
  spedizioneId: string, orderNumber: string, _prev: StatoAzione, _formData: FormData,
): Promise<StatoAzione> {
  const { error } = await shippingClient.POST("/spedizioni/{spedizione_id}/conferma", {
    params: { path: { spedizione_id: spedizioneId } },
  });
  if (error) return { errore: messaggioErrore(error) };
  revalidatePath(`/spedizioni/${orderNumber}`);
  return { errore: null };
}

// EFFETTO REALE: prenota il ritiro DHL vero.
export async function richiediPickupAction(
  spedizioneId: string, orderNumber: string, _prev: StatoAzione, formData: FormData,
): Promise<StatoAzione> {
  const dataPickup = formData.get("data_pickup");
  const { error } = await shippingClient.POST("/spedizioni/{spedizione_id}/pickup", {
    params: {
      path: { spedizione_id: spedizioneId },
      query: { data_pickup: typeof dataPickup === "string" && dataPickup ? dataPickup : undefined },
    },
  });
  if (error) return { errore: messaggioErrore(error) };
  revalidatePath(`/spedizioni/${orderNumber}`);
  return { errore: null };
}

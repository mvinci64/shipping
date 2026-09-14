"use server";

import { revalidatePath } from "next/cache";
import { shippingClient } from "@/lib/shipping-client";

export type StatoPickupMultiplo = { errore: string | null; successo: string | null };

function messaggioErrore(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg).filter(Boolean).join("; ");
    if (detail && typeof detail === "object") return JSON.stringify(detail);
  }
  return "Errore sconosciuto";
}

// EFFETTO REALE: un solo ritiro DHL vero per tutte le spedizioni scelte
// (un solo passaggio del corriere) — vedi shipping-api POST
// /spedizioni/pickup-multiplo.
export async function richiediPickupMultiploAction(
  _prev: StatoPickupMultiplo, formData: FormData,
): Promise<StatoPickupMultiplo> {
  const spedizioneIds = formData.getAll("spedizione_id").filter((v): v is string => typeof v === "string");
  if (spedizioneIds.length < 2) {
    return { errore: "Seleziona almeno due spedizioni confermate per un ritiro unico.", successo: null };
  }
  const dataPickup = formData.get("data_pickup");

  const { data, error } = await shippingClient.POST("/spedizioni/pickup-multiplo", {
    body: {
      spedizione_ids: spedizioneIds,
      data_pickup: typeof dataPickup === "string" && dataPickup ? dataPickup : null,
    },
  });
  if (error) return { errore: messaggioErrore(error), successo: null };

  revalidatePath("/spedizioni");
  return { errore: null, successo: `Ritiro unico richiesto per ${data.length} spedizioni.` };
}

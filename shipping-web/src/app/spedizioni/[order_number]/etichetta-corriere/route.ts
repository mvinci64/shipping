import { shippingClient } from "@/lib/shipping-client";

// Proxy: il browser parla solo con shipping-web, mai direttamente con
// shipping-api. A differenza delle etichette colli/scatolone, questa
// richiede prima di risolvere order_number -> spedizione_id (lo
// spedizione_id non è nell'URL: la pagina di dettaglio è per ordine).
export async function GET(_request: Request, ctx: RouteContext<"/spedizioni/[order_number]/etichetta-corriere">) {
  const { order_number } = await ctx.params;

  const spedizione = await shippingClient.GET("/spedizioni/per-ordine/{order_number}", {
    params: { path: { order_number } },
  });
  if (!spedizione.data) {
    return new Response("Nessuna spedizione per questo ordine", { status: 404 });
  }

  const { data, response } = await shippingClient.GET("/spedizioni/{spedizione_id}/etichetta", {
    params: { path: { spedizione_id: spedizione.data.id } },
    parseAs: "arrayBuffer",
  });

  if (!response.ok || !data) {
    return new Response("Etichetta non disponibile (spedizione non confermata?)", { status: response.status || 404 });
  }

  return new Response(data, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="dhl_${order_number}.pdf"`,
    },
  });
}

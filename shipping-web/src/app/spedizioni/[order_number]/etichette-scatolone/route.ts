import { shippingClient } from "@/lib/shipping-client";

// Proxy: il browser parla solo con shipping-web, mai direttamente con
// shipping-api (stessa scelta della home page — vedi README.md).
export async function GET(_request: Request, ctx: RouteContext<"/spedizioni/[order_number]/etichette-scatolone">) {
  const { order_number } = await ctx.params;
  const { data, response } = await shippingClient.GET("/cartonizzazioni/{order_number}/etichette-scatolone", {
    params: { path: { order_number } },
    parseAs: "arrayBuffer",
  });

  if (!response.ok || !data) {
    return new Response("Etichetta scatolone non disponibile", { status: response.status || 502 });
  }

  return new Response(data, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="etichette_scatolone_${order_number}.pdf"`,
    },
  });
}

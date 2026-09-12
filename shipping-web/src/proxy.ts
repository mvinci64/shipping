import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { AUTH_COOKIE_NAME } from "@/lib/auth-cookie";

// Next.js 16: "middleware" è deprecato in favore di "proxy" (stessa cosa,
// nome nuovo — vedi node_modules/next/dist/docs/.../proxy.md).
export async function proxy(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const shippingApiUrl = process.env.SHIPPING_API_URL ?? "http://localhost:8000";
  const risposta = await fetch(`${shippingApiUrl}/auth/session`, {
    headers: { authorization: `Bearer ${token}` },
  }).catch(() => null);

  if (!risposta || !risposta.ok) {
    const redirectResponse = NextResponse.redirect(new URL("/login", request.url));
    redirectResponse.cookies.delete(AUTH_COOKIE_NAME);
    return redirectResponse;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"],
};

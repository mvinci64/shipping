import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { AUTH_COOKIE_NAME } from "@/lib/auth-cookie";
import { shippingClient } from "@/lib/shipping-client";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;
  if (token) {
    await shippingClient.POST("/auth/logout", { body: { token } }).catch(() => null);
  }
  cookieStore.delete(AUTH_COOKIE_NAME);
  return NextResponse.redirect(new URL("/login", request.url));
}

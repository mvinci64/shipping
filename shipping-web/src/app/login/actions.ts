"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { shippingClient } from "@/lib/shipping-client";
import { AUTH_COOKIE_NAME } from "@/lib/auth-cookie";

export type StatoLogin = { errore: string | null };

function messaggioErrore(status: number | undefined): string {
  if (status === 403) return "Account non abilitato al reparto spedizioni.";
  return "Email o password non corrette.";
}

export async function loginAction(_prev: StatoLogin, formData: FormData): Promise<StatoLogin> {
  const email = formData.get("email");
  const password = formData.get("password");
  if (typeof email !== "string" || typeof password !== "string" || !email || !password) {
    return { errore: "Inserisci email e password." };
  }

  const { data, response } = await shippingClient
    .POST("/auth/login", { body: { email, password } })
    .catch((cause) => ({
      data: undefined,
      error: { detail: cause instanceof Error ? cause.message : String(cause) },
      response: undefined,
    }));

  if (!data) return { errore: messaggioErrore(response?.status) };

  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE_NAME, data.token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    expires: new Date(data.expires_at),
  });

  redirect("/spedizioni");
}

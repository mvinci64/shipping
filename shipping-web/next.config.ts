import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fissa esplicitamente la root del workspace Turbopack alla root del
  // repo (non a questa cartella): senza questo, Next.js risale l'albero
  // delle directory, trova un package-lock.json estraneo nella home
  // dell'utente e inferisce una root sbagliata — ma la root deve
  // comunque includere ../client-ts, dipendenza locale collegata via
  // symlink (file:../client-ts), altrimenti Turbopack non può seguirlo
  // fuori dalla propria root.
  turbopack: {
    root: path.join(__dirname, ".."),
  },
  // ../client-ts è un pacchetto locale (file:) distribuito come sorgente
  // TS, non pre-compilato in JS — senza transpilePackages Next.js non lo
  // fa passare dal proprio compilatore e la risoluzione del modulo fallisce.
  transpilePackages: ["@viscotta/shipping-client"],
};

export default nextConfig;

"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Link } from "@/i18n/routing";

const COOKIE_NAME = "eg_consent";
const COOKIE_MAX_AGE = 31536000;

const COPY: Record<
  string,
  { title: string; body: string; accept: string; deny: string; learnMore: string }
> = {
  de: {
    title: "Cookie-Einstellungen",
    body: "EstateGap verwendet notwendige Cookies fur Anmeldung und Spracheinstellungen. Optionale Analyse-Skripte werden erst geladen, wenn Sie zustimmen.",
    accept: "Akzeptieren",
    deny: "Ablehnen",
    learnMore: "Datenschutz lesen",
  },
  en: {
    title: "Cookie settings",
    body: "EstateGap uses essential cookies for sign-in and language preferences. Optional analytics scripts stay blocked until you grant consent.",
    accept: "Accept",
    deny: "Deny",
    learnMore: "Read the privacy policy",
  },
  es: {
    title: "Configuracion de cookies",
    body: "EstateGap usa cookies esenciales para el acceso y el idioma. Los scripts de analitica opcionales siguen bloqueados hasta que des su consentimiento.",
    accept: "Aceptar",
    deny: "Rechazar",
    learnMore: "Leer la politica de privacidad",
  },
  fr: {
    title: "Parametres des cookies",
    body: "EstateGap utilise des cookies essentiels pour la connexion et la langue. Les scripts analytiques optionnels restent bloques jusqu'a votre consentement.",
    accept: "Accepter",
    deny: "Refuser",
    learnMore: "Voir la politique de confidentialite",
  },
  it: {
    title: "Impostazioni cookie",
    body: "EstateGap usa cookie essenziali per accesso e lingua. Gli script analitici opzionali restano bloccati finche non dai il consenso.",
    accept: "Accetta",
    deny: "Rifiuta",
    learnMore: "Leggi l'informativa privacy",
  },
  pt: {
    title: "Preferencias de cookies",
    body: "A EstateGap usa cookies essenciais para sessao e idioma. Os scripts analiticos opcionais ficam bloqueados ate dar consentimento.",
    accept: "Aceitar",
    deny: "Recusar",
    learnMore: "Ler a politica de privacidade",
  },
};

function readConsentCookie() {
  if (typeof document === "undefined") {
    return "";
  }

  const entry = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${COOKIE_NAME}=`));

  if (!entry) {
    return "";
  }

  return entry.split("=")[1] ?? "";
}

function writeConsentCookie(value: "granted" | "denied") {
  const parts = [
    `${COOKIE_NAME}=${value}`,
    `Max-Age=${COOKIE_MAX_AGE}`,
    "Path=/",
    "SameSite=Lax",
  ];

  if (window.location.protocol === "https:") {
    parts.push("Secure");
  }

  document.cookie = parts.join("; ");
}

export function CookieConsent() {
  const locale = useLocale();
  const copy = COPY[locale] ?? COPY.en;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(readConsentCookie() === "");
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-xl">
        <div className="space-y-4">
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold text-slate-950">{copy.title}</h2>
            <p className="text-sm leading-7 text-slate-600">{copy.body}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={() => {
                writeConsentCookie("granted");
                setOpen(false);
              }}
              type="button"
            >
              {copy.accept}
            </Button>
            <Button
              onClick={() => {
                writeConsentCookie("denied");
                setOpen(false);
              }}
              type="button"
              variant="outline"
            >
              {copy.deny}
            </Button>
            <Link className="text-sm font-medium text-teal-700" href="/privacy">
              {copy.learnMore}
            </Link>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

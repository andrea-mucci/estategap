import { createNavigation } from "next-intl/navigation";
import { defineRouting } from "next-intl/routing";

export const locales = [
  "en",
  "es",
  "fr",
  "it",
  "de",
  "pt",
  "nl",
  "pl",
  "sv",
  "el",
] as const;

export type AppLocale = (typeof locales)[number];

export const defaultLocale: AppLocale = "en";

export const localeLabels: Record<AppLocale, string> = {
  en: "English",
  es: "Español",
  fr: "Français",
  it: "Italiano",
  de: "Deutsch",
  pt: "Português",
  nl: "Nederlands",
  pl: "Polski",
  sv: "Svenska",
  el: "Ελληνικά",
};

export const routing = defineRouting({
  locales: [...locales],
  defaultLocale,
  localePrefix: "always",
});

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);

import type { MetadataRoute } from "next";

import { routing } from "@/i18n/routing";

const baseUrl = "https://estategap.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const alternates = Object.fromEntries(
    routing.locales.map((locale) => [locale, `${baseUrl}/${locale}`]),
  );

  return routing.locales.map((locale) => ({
    url: `${baseUrl}/${locale}`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 1,
    alternates: {
      languages: alternates,
    },
  }));
}

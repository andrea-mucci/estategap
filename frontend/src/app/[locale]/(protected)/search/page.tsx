import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SearchPage } from "@/components/search/SearchPage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("meta");

  return {
    title: t("searchTitle"),
  };
}

export default async function SearchRoutePage() {
  return <SearchPage />;
}

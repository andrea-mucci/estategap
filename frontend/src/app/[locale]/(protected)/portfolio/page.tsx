import type { Metadata } from "next";
import { Suspense } from "react";
import { getTranslations } from "next-intl/server";

import { PortfolioClient } from "@/components/portfolio/PortfolioClient";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { requireSession } from "@/lib/auth";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });

  return {
    title: t("portfolio"),
  };
}

export default async function PortfolioPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  await requireSession(locale);
  const t = await getTranslations({ locale, namespace: "nav" });

  return (
    <section className="space-y-6">
      <h1 className="text-3xl font-semibold text-slate-950">{t("portfolio")}</h1>
      <Suspense fallback={<LoadingSkeleton rows={5} />}>
        <PortfolioClient />
      </Suspense>
    </section>
  );
}

import { getTranslations } from "next-intl/server";

import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

export default async function PortfolioPage() {
  const t = await getTranslations("nav");

  return (
    <section className="space-y-6">
      <h1 className="text-3xl font-semibold text-slate-950">{t("portfolio")}</h1>
      <LoadingSkeleton rows={3} />
    </section>
  );
}

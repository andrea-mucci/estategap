import { getTranslations } from "next-intl/server";

export default async function LocaleHomePage() {
  const t = await getTranslations("meta");

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <section className="max-w-3xl rounded-[40px] border border-white/70 bg-white/90 p-10 text-center shadow-2xl">
        <p className="text-sm font-semibold uppercase tracking-[0.26em] text-teal-700">
          EstateGap
        </p>
        <h1 className="mt-4 text-5xl font-semibold tracking-tight text-slate-950">
          {t("appName")}
        </h1>
        <p className="mt-6 text-lg leading-8 text-slate-600">{t("tagline")}</p>
      </section>
    </main>
  );
}

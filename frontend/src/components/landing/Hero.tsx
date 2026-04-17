import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";

export default async function Hero() {
  const t = await getTranslations("landing.hero");
  const proofPoints = t.raw("proofPoints") as string[];

  return (
    <section className="mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:px-8 lg:py-24">
      <div className="space-y-8">
        <div className="space-y-5">
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-700">
            {t("eyebrow")}
          </p>
          <h1 className="max-w-4xl text-5xl font-semibold tracking-tight text-slate-950 sm:text-6xl lg:text-7xl">
            {t("headline")}
          </h1>
          <p className="max-w-2xl text-lg leading-8 text-slate-600 sm:text-xl">
            {t("subheadline")}
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link data-testid="hero-primary-cta" href="/register?tier=free">
              {t("primaryCta")}
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/#features">{t("secondaryCta")}</Link>
          </Button>
        </div>

        <ul className="grid gap-3 text-sm text-slate-600 sm:grid-cols-3">
          {proofPoints.map((item) => (
            <li
              className="rounded-[24px] border border-white/70 bg-white/70 px-4 py-4 shadow-[0_22px_50px_-40px_rgba(15,23,42,0.55)]"
              key={item}
            >
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="relative">
        <div className="absolute -left-6 top-12 h-32 w-32 rounded-full bg-teal-200/60 blur-3xl" />
        <div className="absolute bottom-0 right-4 h-36 w-36 rounded-full bg-orange-200/60 blur-3xl" />
        <div className="animate-float relative overflow-hidden rounded-[36px] border border-white/80 bg-slate-950 p-6 text-white shadow-[0_45px_120px_-55px_rgba(15,23,42,0.8)]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.24),transparent_36%),radial-gradient(circle_at_bottom_right,rgba(251,146,60,0.18),transparent_28%)]" />
          <div className="relative">
            <div className="flex items-center justify-between text-sm text-teal-100/80">
              <span>{t("cardLabel")}</span>
              <span className="rounded-full bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.2em]">
                Live
              </span>
            </div>
            <h2 className="mt-6 max-w-sm text-3xl font-semibold leading-tight">
              {t("cardTitle")}
            </h2>
            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">
                  {t("cardMetricLabel")}
                </p>
                <p className="mt-4 text-4xl font-semibold">{t("cardMetricValue")}</p>
              </div>
              <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">
                  {t("cardSecondaryMetricLabel")}
                </p>
                <p className="mt-4 text-4xl font-semibold">{t("cardSecondaryMetricValue")}</p>
              </div>
            </div>
            <div className="mt-8 h-48 rounded-[28px] border border-white/10 bg-white/5 p-4">
              <svg aria-hidden className="h-full w-full" viewBox="0 0 320 160">
                <defs>
                  <linearGradient id="marketLine" x1="0%" x2="100%" y1="0%" y2="0%">
                    <stop offset="0%" stopColor="#5eead4" />
                    <stop offset="100%" stopColor="#fb923c" />
                  </linearGradient>
                </defs>
                <path
                  d="M12 116C34 109 54 94 78 92C104 90 119 115 145 112C166 109 177 68 205 63C233 58 250 91 277 86C294 83 304 70 308 64"
                  fill="none"
                  stroke="url(#marketLine)"
                  strokeLinecap="round"
                  strokeWidth="7"
                />
                <circle cx="78" cy="92" fill="#5eead4" r="7" />
                <circle cx="205" cy="63" fill="#f97316" r="7" />
                <circle cx="277" cy="86" fill="#5eead4" r="7" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

"use client";

import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";

export default function LandingNav() {
  const t = useTranslations("landing.nav");

  return (
    <header className="sticky top-0 z-40 border-b border-white/60 bg-white/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <Link className="space-y-1" href="/">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-teal-700">
            EstateGap
          </p>
          <p className="text-lg font-semibold text-slate-950">Market Sourcing OS</p>
        </Link>

        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link className="hidden text-sm font-medium text-slate-600 transition hover:text-slate-950 sm:inline-flex" href="/login">
            {t("login")}
          </Link>
          <Button asChild>
            <Link href="/register?tier=free">{t("cta")}</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}

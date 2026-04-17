"use client";

import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { Link } from "@/i18n/routing";

export default function LandingFooter() {
  const t = useTranslations("landing.footer");

  return (
    <footer className="border-t border-white/60 bg-white/70">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-700">
            EstateGap
          </p>
          <p className="mt-3 max-w-xl text-sm leading-7 text-slate-600">{t("tagline")}</p>
          <p className="mt-4 text-sm text-slate-500">© {new Date().getFullYear()} EstateGap</p>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          <div className="flex flex-wrap gap-4 text-sm text-slate-600">
            <Link href="/privacy">{t("privacy")}</Link>
            <Link href="/terms">{t("terms")}</Link>
            <Link href="/contact">{t("contact")}</Link>
            <a href="https://github.com/estategap" rel="noreferrer" target="_blank">
              {t("github")}
            </a>
          </div>
          <LanguageSwitcher />
        </div>
      </div>
    </footer>
  );
}

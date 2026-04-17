"use client";

import { useEffect, useEffectEvent, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/routing";
import { useOnboarding } from "@/hooks/useOnboarding";
import { useChatStore } from "@/stores/chatStore";

type HighlightBox = {
  height: number;
  left: number;
  top: number;
  width: number;
};

function normalizeCriteria(criteria: Record<string, unknown> | Record<string, string> | null) {
  if (!criteria) {
    return {};
  }

  return Object.entries(criteria).reduce<Record<string, string>>((accumulator, [key, value]) => {
    if (value == null) {
      return accumulator;
    }

    const normalized = `${value}`.trim();
    if (!normalized) {
      return accumulator;
    }

    accumulator[key] = normalized;
    return accumulator;
  }, {});
}

function criteriaToQuery(criteria: Record<string, string>) {
  const query = new URLSearchParams();
  const country = criteria.country ?? criteria.country_code;
  const maxPrice = criteria.maxPrice ?? criteria.max_price_eur ?? criteria.budget_max;
  const minArea = criteria.minArea ?? criteria.min_area_m2 ?? criteria.area_min;
  const propertyType = criteria.propertyType ?? criteria.property_type;

  if (country) {
    query.set("country", country);
  }
  if (maxPrice) {
    query.set("maxPrice", maxPrice);
  }
  if (minArea) {
    query.set("minArea", minArea);
  }
  if (propertyType) {
    query.set("propertyType", propertyType);
  }

  return query.toString();
}

export default function OnboardingTour() {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations("onboarding");
  const { active, advance, chatCriteria, currentStep, showUpgradeOptions, skip } = useOnboarding();
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const sessions = useChatStore((state) => state.sessions);
  const [highlight, setHighlight] = useState<HighlightBox | null>(null);

  const activeSession = activeSessionId ? sessions.get(activeSessionId) : null;
  const criteria = useMemo(
    () => normalizeCriteria((chatCriteria as Record<string, unknown> | null) ?? activeSession?.criteria ?? null),
    [activeSession?.criteria, chatCriteria],
  );

  const homePath = `/${locale}/home`;
  const chatPath = `/${locale}/chat`;
  const alertsPath = `/${locale}/alerts`;
  const dashboardPath = `/${locale}/dashboard`;

  useEffect(() => {
    if (!active) {
      return;
    }

    if (currentStep === "CHAT" && pathname !== homePath && pathname !== chatPath) {
      router.push("/home");
      return;
    }

    if (currentStep === "ALERT" && pathname !== alertsPath) {
      const query = criteriaToQuery(criteria);
      router.push(query ? `/alerts?${query}` : "/alerts");
      return;
    }

    if (currentStep === "DASHBOARD" && pathname !== dashboardPath) {
      router.push("/dashboard");
    }
  }, [active, alertsPath, criteria, currentStep, dashboardPath, homePath, pathname, router, chatPath]);

  useEffect(() => {
    if (!active || currentStep !== "CHAT" || pathname !== chatPath || !activeSession) {
      return;
    }

    const hasUserMessage = activeSession.messages.some((message) => message.role === "user");
    if (!hasUserMessage) {
      return;
    }

    const timeout = window.setTimeout(() => {
      advance(Object.keys(criteria).length > 0 ? criteria : null);
    }, Object.keys(criteria).length > 0 ? 200 : 1400);

    return () => window.clearTimeout(timeout);
  }, [active, activeSession, advance, chatPath, criteria, currentStep, pathname]);

  const updateHighlight = useEffectEvent(() => {
    const selector =
      currentStep === "CHAT"
        ? "#chat-input"
        : currentStep === "ALERT"
          ? "#alert-form"
          : currentStep === "DASHBOARD"
            ? "#dashboard-summary-card"
            : null;

    if (!selector) {
      setHighlight(null);
      return;
    }

    const element = document.querySelector(selector);
    if (!(element instanceof HTMLElement)) {
      setHighlight(null);
      return;
    }

    const rect = element.getBoundingClientRect();
    setHighlight({
      height: rect.height + 16,
      left: rect.left - 8,
      top: rect.top - 8,
      width: rect.width + 16,
    });
  });

  useEffect(() => {
    if (!active) {
      setHighlight(null);
      return;
    }

    const selector =
      currentStep === "CHAT"
        ? "#chat-input"
        : currentStep === "ALERT"
          ? "#alert-form"
          : currentStep === "DASHBOARD"
            ? "#dashboard-summary-card"
            : null;

    const target = selector ? document.querySelector(selector) : null;
    if (target instanceof HTMLElement) {
      target.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "nearest",
      });
    }

    updateHighlight();
    const delayedUpdate = window.setTimeout(() => updateHighlight(), 220);

    const handleUpdate = () => updateHighlight();
    window.addEventListener("resize", handleUpdate);
    window.addEventListener("scroll", handleUpdate, true);

    return () => {
      window.clearTimeout(delayedUpdate);
      window.removeEventListener("resize", handleUpdate);
      window.removeEventListener("scroll", handleUpdate, true);
    };
  }, [active, currentStep, pathname, updateHighlight]);

  if (!active || !highlight) {
    return null;
  }

  const content =
    currentStep === "CHAT"
      ? t.raw("step1")
      : currentStep === "ALERT"
        ? t.raw("step2")
        : t.raw("step3");

  const stepNumber = currentStep === "CHAT" ? "01" : currentStep === "ALERT" ? "02" : "03";

  return (
    <>
      <div className="pointer-events-none fixed inset-0 z-[70] bg-slate-950/45">
        <div
          className="absolute rounded-[32px] border-2 border-teal-400 shadow-[0_0_0_9999px_rgba(15,23,42,0.45)] transition-all duration-300"
          style={highlight}
        />
      </div>

      <aside className="pointer-events-auto fixed bottom-6 right-6 z-[80] w-[min(28rem,calc(100vw-2rem))] rounded-[32px] border border-white/80 bg-white/95 p-6 shadow-[0_40px_110px_-55px_rgba(15,23,42,0.8)]">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-700">
          Step {stepNumber}
        </p>
        <h2 className="mt-3 text-2xl font-semibold text-slate-950">{content.title}</h2>
        <p className="mt-3 text-sm leading-7 text-slate-600">{content.body}</p>
        <p className="mt-4 text-sm font-medium text-slate-500">{content.hint}</p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {currentStep === "DASHBOARD" ? (
            <Button onClick={showUpgradeOptions}>{t("finish")}</Button>
          ) : null}
          <Button onClick={() => void skip()} variant="ghost">
            {t("skip")}
          </Button>
        </div>
      </aside>
    </>
  );
}

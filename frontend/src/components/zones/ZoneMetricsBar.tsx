"use client";

import { useLocale } from "next-intl";

import { Card, CardContent } from "@/components/ui/card";
import { convertFromEUR, formatCurrency } from "@/lib/currency";
import type { ZoneAnalytics } from "@/lib/api";

function formatPercent(value: number, locale: string) {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(value);
}

export function ZoneMetricsBar({
  analytics,
  rates,
  preferredCurrency,
}: {
  analytics: ZoneAnalytics;
  rates: Record<string, number>;
  preferredCurrency: string;
}) {
  const locale = useLocale();
  const months = analytics.months;
  const first = months[0];
  const last = months[months.length - 1];

  const trendPct =
    first && last && first.median_price_m2_eur > 0
      ? ((last.median_price_m2_eur - first.median_price_m2_eur) /
          first.median_price_m2_eur) *
        100
      : 0;
  const totalVolume = months.reduce((sum, month) => sum + month.listing_count, 0);
  const dealFrequency =
    last && last.listing_count > 0 ? (last.deal_count / last.listing_count) * 100 : 0;

  const metrics = [
    {
      label: "Median price / m²",
      value: last
        ? formatCurrency(
            convertFromEUR(last.median_price_m2_eur, preferredCurrency, rates),
            preferredCurrency,
            locale,
          )
        : "—",
    },
    {
      label: "12-month trend",
      value: `${trendPct >= 0 ? "+" : ""}${formatPercent(trendPct, locale)}%`,
    },
    {
      label: "Total volume",
      value: totalVolume.toLocaleString(locale),
    },
    {
      label: "Avg. days on market",
      value: last ? `${formatPercent(last.avg_days_on_market, locale)} d` : "—",
    },
    {
      label: "Inventory",
      value: last ? last.listing_count.toLocaleString(locale) : "—",
    },
    {
      label: "Deal frequency",
      value: `${formatPercent(dealFrequency, locale)}%`,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      {metrics.map((metric) => (
        <Card key={metric.label}>
          <CardContent className="space-y-2 pt-6">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {metric.label}
            </p>
            <p className="text-2xl font-semibold text-slate-950">{metric.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

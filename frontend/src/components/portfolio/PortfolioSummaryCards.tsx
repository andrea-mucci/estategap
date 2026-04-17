"use client";

import { useLocale } from "next-intl";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PortfolioSummary } from "@/lib/api";
import { convertFromEUR, formatCurrency } from "@/lib/currency";

const summaryCards = [
  {
    key: "total_invested_eur",
    label: "Total invested",
  },
  {
    key: "total_current_value_eur",
    label: "Current value",
  },
  {
    key: "unrealized_gain_loss_eur",
    label: "Unrealized gain / loss",
  },
  {
    key: "average_rental_yield_pct",
    label: "Avg rental yield",
  },
] as const;

export function PortfolioSummaryCards({
  summary,
  isLoading,
  rates,
  preferredCurrency,
}: {
  summary: PortfolioSummary | null;
  isLoading: boolean;
  rates: Record<string, number>;
  preferredCurrency: string;
}) {
  const locale = useLocale();

  if (isLoading) {
    return (
      <div className="grid gap-4 xl:grid-cols-4">
        {summaryCards.map((card) => (
          <Card key={card.key}>
            <CardContent className="space-y-4 pt-6">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-10 w-32" />
              <Skeleton className="h-3 w-20" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const safeSummary = summary ?? {
    total_properties: 0,
    total_invested_eur: 0,
    total_current_value_eur: 0,
    unrealized_gain_loss_eur: 0,
    unrealized_gain_loss_pct: 0,
    average_rental_yield_pct: 0,
    properties_with_estimate: 0,
  };

  return (
    <div className="grid gap-4 xl:grid-cols-4">
      {summaryCards.map((card) => {
        const isYield = card.key === "average_rental_yield_pct";
        const isGainLoss = card.key === "unrealized_gain_loss_eur";
        const gainLossPositive = safeSummary.unrealized_gain_loss_eur >= 0;

        let value = "0";
        let caption = `${safeSummary.total_properties.toLocaleString(locale)} properties tracked`;

        if (isYield) {
          value = `${safeSummary.average_rental_yield_pct.toFixed(1)}%`;
        } else {
          const rawValue = safeSummary[card.key];
          value = formatCurrency(
            convertFromEUR(rawValue, preferredCurrency, rates),
            preferredCurrency,
            locale,
          );
        }

        if (isGainLoss) {
          caption = `${safeSummary.unrealized_gain_loss_pct >= 0 ? "+" : ""}${safeSummary.unrealized_gain_loss_pct.toFixed(1)}% vs. invested`;
        }

        if (card.key === "total_current_value_eur") {
          const withoutEstimate =
            safeSummary.total_properties - safeSummary.properties_with_estimate;
          caption = `${safeSummary.properties_with_estimate.toLocaleString(locale)} with estimates, ${withoutEstimate.toLocaleString(locale)} without`;
        }

        return (
          <Card key={card.key}>
            <CardContent className="pt-6">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {card.label}
              </p>
              <p
                className={
                  isGainLoss
                    ? `mt-4 text-4xl font-semibold ${gainLossPositive ? "text-emerald-700" : "text-rose-700"}`
                    : "mt-4 text-4xl font-semibold text-slate-950"
                }
              >
                {value}
              </p>
              <p className="mt-3 text-sm text-slate-500">{caption}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

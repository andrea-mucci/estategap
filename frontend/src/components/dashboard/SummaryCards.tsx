"use client";

import {
  ArrowDownRight,
  Building2,
  Star,
  TrendingUp,
} from "lucide-react";
import { useLocale } from "next-intl";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { formatCompactNumber } from "@/lib/utils";

const cards = [
  {
    key: "total_listings",
    label: "Total listings",
    icon: Building2,
  },
  {
    key: "new_today",
    label: "New today",
    icon: TrendingUp,
  },
  {
    key: "tier1_deals_today",
    label: "Tier 1 deals today",
    icon: Star,
  },
  {
    key: "price_drops_7d",
    label: "Price drops (7d)",
    icon: ArrowDownRight,
  },
] as const;

export function SummaryCards({ country }: { country: string }) {
  const locale = useLocale();
  const query = useDashboardSummary(country);

  if (query.isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((item) => (
          <Card key={item.key}>
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

  if (query.isError || !query.data) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-slate-600">
          Dashboard summary is unavailable right now.
        </CardContent>
      </Card>
    );
  }

  const summary = query.data;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((item) => {
        const Icon = item.icon;
        const value = summary[item.key];

        return (
          <Card key={item.key}>
            <CardContent className="pt-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {item.label}
                  </p>
                  <p className="mt-4 text-4xl font-semibold text-slate-950">
                    {value === 0 ? "0" : formatCompactNumber(value, locale)}
                  </p>
                </div>
                <span className="rounded-2xl bg-teal-50 p-3 text-teal-700">
                  <Icon className="h-5 w-5" />
                </span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

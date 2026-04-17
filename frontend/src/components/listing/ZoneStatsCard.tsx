"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExtendedListingDetail } from "@/lib/listing-search";
import { formatCompactNumber, formatCurrency } from "@/lib/utils";

export function ZoneStatsCard({
  listing,
  locale,
}: {
  listing: ExtendedListingDetail;
  locale: string;
}) {
  const t = useTranslations("listingDetail");
  if (!listing.zone_stats) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("zoneSnapshot")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">{t("zoneDataUnavailable")}</p>
        </CardContent>
      </Card>
    );
  }

  const trend = listing.zone_stats.price_trend_pct ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{listing.zone_stats.zone_name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric
            label={t("zoneMetricMedianPrice")}
            value={formatCurrency(listing.zone_stats.median_price_m2_eur, "EUR", locale)}
          />
          <Metric
            label={t("zoneMetricListings")}
            value={formatCompactNumber(listing.zone_stats.listing_count, locale)}
          />
          <Metric
            label={t("zoneMetricDeals")}
            value={formatCompactNumber(listing.zone_stats.deal_count, locale)}
          />
          <div className="rounded-3xl bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              {t("zoneMetricTrend")}
            </p>
            {trend == null ? (
              <p className="mt-2 text-lg font-semibold text-slate-500">—</p>
            ) : (
              <p
                className={`mt-2 inline-flex items-center gap-2 text-lg font-semibold ${
                  trend >= 0 ? "text-emerald-600" : "text-rose-600"
                }`}
              >
                {trend >= 0 ? (
                  <ArrowUpRight className="h-4 w-4" />
                ) : (
                  <ArrowDownRight className="h-4 w-4" />
                )}
                {`${Math.abs(trend).toFixed(1)}%`}
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-3xl bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

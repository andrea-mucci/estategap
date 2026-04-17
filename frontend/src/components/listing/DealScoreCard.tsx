"use client";

import { useTranslations } from "next-intl";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExtendedListingDetail } from "@/lib/listing-search";
import { getDealTierDescription, getDealTierMeta } from "@/lib/listing-search";
import { formatCurrency } from "@/lib/utils";

export function DealScoreCard({
  listing,
  locale,
}: {
  listing: ExtendedListingDetail;
  locale: string;
}) {
  const t = useTranslations("listingDetail");
  const tierMeta = getDealTierMeta(listing.deal_tier);
  const tierDescription = getDealTierDescription(t, tierMeta.value);

  if (listing.estimated_price == null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("dealAnalysis")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">{t("analysisUnavailable")}</p>
        </CardContent>
      </Card>
    );
  }

  const gapPct = listing.asking_price_eur
    ? ((listing.estimated_price - listing.asking_price_eur) / listing.asking_price_eur) * 100
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("dealAnalysis")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-slate-500">{t("estimatedFairPrice")}</p>
          <p className="text-3xl font-semibold text-slate-950">
            {formatCurrency(listing.estimated_price, "EUR", locale)}
          </p>
        </div>
        <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-600">
          {`${formatCurrency(listing.confidence_low, "EUR", locale)} — ${formatCurrency(
            listing.confidence_high,
            "EUR",
            locale,
          )}`}
        </div>
        {gapPct != null ? (
          <p className={gapPct >= 0 ? "text-emerald-600" : "text-rose-600"}>
            {gapPct >= 0
              ? t("belowEstimate", {
                  value: Math.abs(gapPct).toFixed(1),
                })
              : t("aboveEstimate", {
                  value: Math.abs(gapPct).toFixed(1),
                })}
          </p>
        ) : null}
        <span className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${tierMeta.tone}`}>
          {`${tierMeta.label} · ${tierDescription}`}
        </span>
      </CardContent>
    </Card>
  );
}

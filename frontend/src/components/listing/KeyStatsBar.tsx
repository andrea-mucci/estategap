"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import type { ExtendedListingDetail } from "@/lib/listing-search";
import { getDealTierMeta } from "@/lib/listing-search";
import { formatCurrency } from "@/lib/utils";

export function KeyStatsBar({
  listing,
  locale,
}: {
  listing: ExtendedListingDetail;
  locale: string;
}) {
  const t = useTranslations("listingDetail");
  const tierMeta = getDealTierMeta(listing.deal_tier);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-[28px] border border-white/70 bg-white/90 p-4">
      <Badge>{formatCurrency(listing.asking_price_eur, listing.currency, locale)}</Badge>
      {listing.asking_price && listing.currency !== "EUR" ? (
        <Badge>{formatCurrency(listing.asking_price, listing.currency, locale)}</Badge>
      ) : null}
      {listing.area_m2 ? <Badge>{`${listing.area_m2} m²`}</Badge> : null}
      {listing.bedrooms ? (
        <Badge>
          {t("keyStats.beds", {
            count: listing.bedrooms,
          })}
        </Badge>
      ) : null}
      {listing.floor_number != null ? (
        <Badge>
          {t("keyStats.floor", {
            floor: listing.floor_number,
          })}
        </Badge>
      ) : null}
      <Badge className={tierMeta.tone}>
        {t("keyStats.tierScore", {
          score: listing.deal_score ?? "—",
          tier: tierMeta.label,
        })}
      </Badge>
    </div>
  );
}

"use client";

import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { ListingCard as ListingCardModel } from "@/types/chat";

export function ListingCard({
  compact = false,
  listing,
}: {
  compact?: boolean;
  listing: ListingCardModel;
}) {
  const locale = useLocale();
  const t = useTranslations("listing");

  const formattedPrice = new Intl.NumberFormat(locale, {
    currency: listing.currency,
    maximumFractionDigits: 0,
    style: "currency",
  }).format(listing.price);

  const dealScoreClassName =
    listing.dealScore >= 70
      ? "bg-green-500 text-white"
      : listing.dealScore >= 40
        ? "bg-amber-500 text-slate-950"
        : "bg-red-500 text-white";

  return (
    <Card className={compact ? "min-w-[260px]" : undefined}>
      <div className="relative h-52 bg-slate-100">
        {listing.photos[0] ? (
          <Image
            alt={listing.title}
            className="object-cover"
            fill
            sizes="(max-width: 768px) 100vw, 320px"
            src={listing.photos[0]}
          />
        ) : null}
      </div>

      <CardContent className="space-y-4 pt-5">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-slate-950">{listing.title}</h3>
          <p className="text-sm text-slate-500">{listing.location}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Badge>{formattedPrice}</Badge>
          <Badge className={dealScoreClassName}>{`${t("dealScore")}: ${listing.dealScore}`}</Badge>
          {listing.bedrooms != null ? <Badge>{`${t("bedrooms")}: ${listing.bedrooms}`}</Badge> : null}
          {listing.areaSqm != null ? <Badge>{`${t("area")}: ${listing.areaSqm} m²`}</Badge> : null}
        </div>
      </CardContent>
    </Card>
  );
}

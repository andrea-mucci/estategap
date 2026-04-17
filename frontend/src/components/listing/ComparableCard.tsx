"use client";

import Image from "next/image";
import { useLocale } from "next-intl";

import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/routing";
import type { ExtendedListingDetail } from "@/lib/listing-search";
import { getDealTierMeta, getListingHeadline, getListingImage } from "@/lib/listing-search";
import { formatCurrency } from "@/lib/utils";

export function ComparableCard({
  comparable,
}: {
  comparable: ExtendedListingDetail;
}) {
  const locale = useLocale();
  const tierMeta = getDealTierMeta(comparable.deal_tier);

  return (
    <Link className="block min-w-[240px]" href={`/listing/${comparable.id}`}>
      <Card className="overflow-hidden">
        <div className="relative h-36 bg-slate-100">
          {getListingImage(comparable) ? (
            <Image
              alt={getListingHeadline(comparable)}
              className="object-cover"
              fill
              sizes="240px"
              src={getListingImage(comparable) as string}
            />
          ) : null}
        </div>
        <CardContent className="space-y-2 pt-4">
          <h3 className="line-clamp-2 font-semibold text-slate-950">
            {getListingHeadline(comparable)}
          </h3>
          <div className="flex flex-wrap gap-2 text-sm text-slate-600">
            <span>{formatCurrency(comparable.asking_price_eur, "EUR", locale)}</span>
            {comparable.area_m2 ? <span>{`${comparable.area_m2} m²`}</span> : null}
          </div>
          <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${tierMeta.tone}`}>
            {tierMeta.label}
          </span>
        </CardContent>
      </Card>
    </Link>
  );
}


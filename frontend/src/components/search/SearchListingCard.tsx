"use client";

import { FileText, Heart, Home, Phone, X } from "lucide-react";
import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/routing";
import type { CrmStatus, ListingSummary } from "@/lib/api";
import {
  getDealTierMeta,
  getDealTierDescription,
  getCrmStatusLabel,
  getListingHeadline,
  getListingImage,
  getListingLocation,
  CRM_STATUS_TONES,
} from "@/lib/listing-search";
import { formatCurrency } from "@/lib/utils";
import { useCrmStore } from "@/stores/crmStore";

function CrmIcon({ status }: { status: NonNullable<CrmStatus> }) {
  if (status === "favorite") return <Heart className="h-3.5 w-3.5" />;
  if (status === "contacted") return <Phone className="h-3.5 w-3.5" />;
  if (status === "visited") return <Home className="h-3.5 w-3.5" />;
  if (status === "offer") return <FileText className="h-3.5 w-3.5" />;
  return <X className="h-3.5 w-3.5" />;
}

export function SearchListingCard({
  crmStatus,
  listing,
  loading = false,
}: {
  crmStatus?: CrmStatus;
  listing?: ListingSummary;
  loading?: boolean;
}) {
  const locale = useLocale();
  const t = useTranslations("listing");
  const tSearch = useTranslations("searchPage");
  const storeStatus = useCrmStore((state) =>
    listing ? state.entries[listing.id] : null,
  );

  if (loading || !listing) {
    return (
      <Card className="overflow-hidden">
        <Skeleton className="h-56 w-full" />
        <CardContent className="space-y-4 pt-6">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <div className="flex gap-2">
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-7 w-16" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const tierMeta = getDealTierMeta(listing.deal_tier);
  const resolvedCrmStatus = storeStatus ?? crmStatus ?? null;
  const image = getListingImage(listing);
  const tierDescription = getDealTierDescription(tSearch, tierMeta.value);

  return (
    <Link className="block" data-testid="listing-card" href={`/listing/${listing.id}`}>
      <Card className="group h-full overflow-hidden transition hover:-translate-y-1 hover:shadow-2xl">
        <div className="relative h-56 bg-slate-100">
          {image ? (
            <Image
              alt={getListingHeadline(listing)}
              className="object-cover transition duration-300 group-hover:scale-[1.03]"
              fill
              sizes="(max-width: 1024px) 100vw, 420px"
              src={image}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-400">
              {t("noImage")}
            </div>
          )}
          {resolvedCrmStatus ? (
            <span
              className={`absolute right-3 top-3 inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${CRM_STATUS_TONES[resolvedCrmStatus]}`}
              title={getCrmStatusLabel(tSearch, resolvedCrmStatus)}
            >
              <CrmIcon status={resolvedCrmStatus} />
              {getCrmStatusLabel(tSearch, resolvedCrmStatus)}
            </span>
          ) : null}
        </div>
        <CardContent className="space-y-4 pt-6">
          <div className="space-y-1">
            <h3 className="line-clamp-2 text-lg font-semibold text-slate-950">
              {getListingHeadline(listing)}
            </h3>
            <p className="line-clamp-1 text-sm text-slate-500">
              {getListingLocation(listing)}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge>{formatCurrency(listing.asking_price_eur, "EUR", locale)}</Badge>
            {listing.area_m2 ? <Badge>{`${listing.area_m2} m²`}</Badge> : null}
            {listing.bedrooms ? (
              <Badge>
                {tSearch("bedroomsShort", {
                  count: listing.bedrooms,
                })}
              </Badge>
            ) : null}
            {listing.days_on_market != null ? (
              <Badge>
                {tSearch("daysShort", {
                  count: listing.days_on_market,
                })}
              </Badge>
            ) : null}
          </div>

          <div className="flex items-center justify-between text-sm">
            <span className={`rounded-full px-3 py-1 font-semibold ${tierMeta.tone}`}>
              {`${tierMeta.label} · ${tierDescription}`}
            </span>
            <span className="font-medium text-slate-600">
              {listing.deal_score != null
                ? tSearch("dealScoreValue", {
                    score: listing.deal_score,
                  })
                : "—"}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

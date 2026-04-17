"use client";

import { FileText, Heart, Home, Phone, X } from "lucide-react";
import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/routing";
import type { CrmStatus, ListingSummary } from "@/lib/api";
import {
  getDealTierMeta,
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

export function SearchListingRow({
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
      <Card className="grid gap-4 overflow-hidden p-4 md:grid-cols-[220px_1fr]">
        <Skeleton className="h-40 w-full" />
        <div className="space-y-4">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
          <div className="flex gap-2">
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-7 w-20" />
          </div>
        </div>
      </Card>
    );
  }

  const tierMeta = getDealTierMeta(listing.deal_tier);
  const resolvedCrmStatus = storeStatus ?? crmStatus ?? null;

  return (
    <Link className="block" data-testid="listing-row" href={`/listing/${listing.id}`}>
      <Card className="grid gap-4 overflow-hidden p-4 transition hover:-translate-y-0.5 hover:shadow-2xl md:grid-cols-[220px_1fr]">
        <div className="relative h-44 overflow-hidden rounded-[24px] bg-slate-100">
          {getListingImage(listing) ? (
            <Image
              alt={getListingHeadline(listing)}
              className="object-cover"
              fill
              sizes="220px"
              src={getListingImage(listing) as string}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-400">
              {t("noImage")}
            </div>
          )}
        </div>
        <div className="flex min-w-0 flex-col justify-between gap-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-2">
              <h3 className="text-xl font-semibold text-slate-950">
                {getListingHeadline(listing)}
              </h3>
              <p className="text-sm text-slate-500">{getListingLocation(listing)}</p>
            </div>
            {resolvedCrmStatus ? (
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${CRM_STATUS_TONES[resolvedCrmStatus]}`}
                title={getCrmStatusLabel(tSearch, resolvedCrmStatus)}
              >
                <CrmIcon status={resolvedCrmStatus} />
                {getCrmStatusLabel(tSearch, resolvedCrmStatus)}
              </span>
            ) : null}
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
                {tSearch("daysLong", {
                  count: listing.days_on_market,
                })}
              </Badge>
            ) : null}
            <Badge className={tierMeta.tone}>{tierMeta.label}</Badge>
          </div>
        </div>
      </Card>
    </Link>
  );
}

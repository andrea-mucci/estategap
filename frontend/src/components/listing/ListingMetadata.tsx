"use client";

import type { ReactNode } from "react";
import { CalendarDays, Clock, ExternalLink } from "lucide-react";
import { format } from "date-fns";
import { useTranslations } from "next-intl";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExtendedListingDetail } from "@/lib/listing-search";

export function ListingMetadata({
  listing,
}: {
  listing: ExtendedListingDetail;
}) {
  const t = useTranslations("listingDetail");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("metadata")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Item label={t("source")} value={listing.source_portal ?? listing.source} />
        <Item
          icon={<CalendarDays className="h-4 w-4" />}
          label={t("published")}
          value={listing.published_at ? format(new Date(listing.published_at), "PPP") : "—"}
        />
        <Item
          icon={<Clock className="h-4 w-4" />}
          label={t("daysOnMarket")}
          value={listing.days_on_market != null ? `${listing.days_on_market}` : "—"}
        />
        <a
          className="inline-flex items-center gap-2 text-sm font-medium text-teal-700 hover:text-teal-800"
          href={listing.source_url}
          rel="noopener noreferrer"
          target="_blank"
        >
          <ExternalLink className="h-4 w-4" />
          {t("openOriginalListing")}
        </a>
      </CardContent>
    </Card>
  );
}

function Item({
  icon,
  label,
  value,
}: {
  icon?: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-3xl bg-slate-50 px-4 py-3">
      <span className="inline-flex items-center gap-2 text-sm text-slate-500">
        {icon}
        {label}
      </span>
      <span className="text-sm font-semibold text-slate-900">{value}</span>
    </div>
  );
}

"use client";

import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";

import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { useListingDetail } from "@/hooks/useListingDetail";
import {
  getListingHeadline,
  getListingLocation,
  type ExtendedListingDetail,
} from "@/lib/listing-search";

import { ComparableCarousel } from "./ComparableCarousel";
import { CrmActions } from "./CrmActions";
import { DealScoreCard } from "./DealScoreCard";
import { DescriptionSection } from "./DescriptionSection";
import { KeyStatsBar } from "./KeyStatsBar";
import { ListingMetadata } from "./ListingMetadata";
import { PhotoGallery } from "./PhotoGallery";
import { PrivateNotes } from "./PrivateNotes";
import { ZoneStatsCard } from "./ZoneStatsCard";

function ListingMiniMapLoading() {
  const t = useTranslations("listingDetail");

  return (
    <div className="flex h-[280px] items-center justify-center rounded-[28px] bg-slate-100 text-sm text-slate-500">
      {t("loadingMap")}
    </div>
  );
}

const ListingMiniMap = dynamic(() => import("./ListingMiniMap"), {
  loading: ListingMiniMapLoading,
  ssr: false,
});

const ShapChart = dynamic(
  () => import("./ShapChart").then((module) => module.ShapChart),
  {
    loading: () => <ChartLoadingCard label="Loading deal analysis…" />,
    ssr: false,
  },
);

const PriceHistoryChart = dynamic(
  () => import("./PriceHistoryChart").then((module) => module.PriceHistoryChart),
  {
    loading: () => <ChartLoadingCard label="Loading price history…" />,
    ssr: false,
  },
);

function ChartLoadingCard({ label }: { label: string }) {
  return (
    <div className="flex h-[280px] items-center justify-center rounded-[28px] bg-slate-100 text-sm text-slate-500">
      {label}
    </div>
  );
}

export function ListingDetailPage({
  initialListing,
}: {
  initialListing: ExtendedListingDetail;
}) {
  const locale = useLocale();
  const query = useListingDetail(initialListing.id, initialListing);

  if (query.isError) {
    return (
      <ErrorDisplay
        error={query.error as Error}
        refetch={() => {
          void query.refetch();
        }}
      />
    );
  }

  const listing = (query.data ?? initialListing) as ExtendedListingDetail;

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-teal-700">
          {listing.country}
        </p>
        <h1 className="text-3xl font-semibold text-slate-950">
          {getListingHeadline(listing)}
        </h1>
        <p className="text-sm text-slate-500">{getListingLocation(listing)}</p>
      </div>
      <PhotoGallery photoUrls={listing.photo_urls} />
      <KeyStatsBar listing={listing} locale={locale} />

      <div className="grid gap-6 xl:grid-cols-2">
        <DealScoreCard listing={listing} locale={locale} />
        <ShapChart listing={listing} />
      </div>

      <PriceHistoryChart listing={listing} locale={locale} />
      <ComparableCarousel comparableIds={listing.comparable_ids} />

      <div className="grid gap-6 xl:grid-cols-2">
        <ZoneStatsCard listing={listing} locale={locale} />
        <ListingMiniMap
          latitude={listing.latitude}
          longitude={listing.longitude}
          pois={listing.zone_stats?.pois ?? undefined}
        />
      </div>

      <DescriptionSection listing={listing} />
      <ListingMetadata listing={listing} />
      <CrmActions listingId={listing.id} />
      <PrivateNotes listingId={listing.id} />
    </section>
  );
}

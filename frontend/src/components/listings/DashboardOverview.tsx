"use client";

import { useTranslations } from "next-intl";

import { ListingCard } from "@/components/listings/ListingCard";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { useListings } from "@/hooks/useListings";

export function DashboardOverview() {
  const t = useTranslations("meta");
  const { data, isPending, isError, error, refetch } = useListings();

  if (isPending) {
    return <LoadingSkeleton rows={4} />;
  }

  if (isError) {
    return <ErrorDisplay error={error as Error} refetch={() => void refetch()} />;
  }

  const items = data?.items ?? [];

  return (
    <section className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-teal-700">
            {t("dashboardTitle")}
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">
            {items.length} listings ready to review
          </h1>
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {items.map((listing) => (
          <ListingCard
            area={listing.area_m2}
            bedrooms={listing.bedrooms}
            city={listing.city ?? undefined}
            dealScore={listing.deal_score}
            href={`/listing/${listing.id}`}
            id={listing.id}
            imageUrl={listing.photo_url ?? undefined}
            key={listing.id}
            price={listing.asking_price_eur}
            title={listing.address ?? listing.city ?? listing.id}
          />
        ))}
      </div>
    </section>
  );
}

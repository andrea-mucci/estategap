"use client";

import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useSession } from "next-auth/react";

import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { createApiClient } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export function ListingDetailView({ id }: { id: string }) {
  const { data: session } = useSession();
  const locale = useLocale();
  const t = useTranslations("listing");

  const query = useQuery({
    queryKey: ["listing", id],
    enabled: Boolean(session?.accessToken),
    queryFn: async () => {
      const client = createApiClient(session?.accessToken);
      const { data, error } = await client.GET("/api/v1/listings/{id}", {
        params: {
          path: { id },
        },
      });

      if (error) {
        throw new Error(error.error || "Failed to load listing");
      }

      return data;
    },
  });

  if (query.isPending) {
    return <LoadingSkeleton rows={6} />;
  }

  if (query.isError) {
    return <ErrorDisplay error={query.error as Error} refetch={() => void query.refetch()} />;
  }

  const listing = query.data;

  if (!listing) {
    return null;
  }

  const image = listing.photo_urls?.[0] || listing.photo_url || "";

  return (
    <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="relative min-h-[360px] overflow-hidden rounded-[32px] bg-slate-100">
        {image ? (
          <Image alt={listing.address ?? listing.id} className="object-cover" fill src={image} />
        ) : (
          <div className="flex h-full items-center justify-center text-slate-400">
            {t("noImage")}
          </div>
        )}
      </div>
      <div className="space-y-4 rounded-[32px] border border-white/60 bg-white/90 p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-teal-700">
          {listing.country}
        </p>
        <h1 className="text-3xl font-semibold text-slate-950">
          {listing.address ?? listing.city ?? listing.id}
        </h1>
        <p className="text-xl font-medium text-slate-700">
          {formatCurrency(listing.asking_price_eur ?? undefined, listing.currency, locale)}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label={t("area")} value={listing.area_m2 ? `${listing.area_m2} m²` : "—"} />
          <Metric label={t("bedrooms")} value={listing.bedrooms ?? "—"} />
          <Metric label={t("bathrooms")} value={listing.bathrooms ?? "—"} />
          <Metric label={t("dealScore")} value={listing.deal_score ?? "—"} />
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-3xl bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

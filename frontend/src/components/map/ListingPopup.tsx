"use client";

import Link from "next/link";
import { useLocale } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchListingDetail } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

function dealTierClassName(tier?: number | null) {
  switch (tier) {
    case 1:
      return "bg-emerald-500 text-white";
    case 2:
      return "bg-blue-500 text-white";
    case 3:
      return "bg-slate-300 text-slate-900";
    case 4:
      return "bg-rose-500 text-white";
    default:
      return "bg-slate-200 text-slate-900";
  }
}

export function ListingPopup({ listingId }: { listingId: string }) {
  const locale = useLocale();
  const { data: session } = useSession();
  const query = useQuery({
    queryKey: ["listing", listingId],
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchListingDetail(session?.accessToken, listingId),
  });

  if (query.isPending) {
    return (
      <div className="w-[260px] space-y-3 p-1">
        <Skeleton className="h-[60px] w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return <div className="w-[260px] text-sm text-slate-500">Listing preview unavailable.</div>;
  }

  const listing = query.data;
  const photo = listing.photo_urls?.[0] ?? listing.photo_url ?? "";

  return (
    <div className="w-[260px] space-y-3" data-testid="mini-listing-card">
      {photo ? (
        <img
          alt={listing.address ?? listing.id}
          className="h-[60px] w-full rounded-2xl object-cover"
          src={photo}
        />
      ) : (
        <div className="flex h-[60px] w-full items-center justify-center rounded-2xl bg-slate-100 text-xs uppercase tracking-[0.18em] text-slate-400">
          No image
        </div>
      )}

      <div className="space-y-2">
        <p className="text-lg font-semibold text-slate-950">
          {formatCurrency(listing.asking_price_eur, listing.currency, locale)}
        </p>
        <div className="flex flex-wrap gap-2">
          <Badge className={dealTierClassName(listing.deal_tier)}>
            Deal {listing.deal_score ?? "—"}
          </Badge>
        </div>
        <p className="text-sm text-slate-600">{listing.address ?? listing.city ?? listing.id}</p>
      </div>

      <Link className="text-sm font-semibold text-teal-700" href={`/${locale}/listing/${listingId}`}>
        View listing
      </Link>
    </div>
  );
}

"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";

import { ChipSelector } from "@/components/chat/ChipSelector";
import { ListingCard } from "@/components/search/ListingCard";
import { MapView } from "@/components/search/MapView";
import { Button } from "@/components/ui/button";
import type { ListingsPage, ListingsSort, SessionStatus } from "@/types/chat";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080").replace(
  /\/$/,
  "",
);

function toQueryString(
  criteria: Record<string, string>,
  sortBy: ListingsSort,
  cursor?: string | null,
) {
  const params = new URLSearchParams();

  const mappings: Record<string, string> = {
    bedrooms: "bedrooms",
    city: "city",
    country: "country",
    maxPrice: "maxPrice",
    minPrice: "minPrice",
    propertyType: "propertyType",
  };

  for (const [key, value] of Object.entries(criteria)) {
    if (!value || !mappings[key]) {
      continue;
    }

    params.set(mappings[key], value);
  }

  params.set("limit", "20");
  params.set("sortBy", sortBy);

  if (cursor) {
    params.set("cursor", cursor);
  }

  return params.toString();
}

export function SearchResults({
  criteria,
  onRefineSearch,
  status,
}: {
  criteria: Record<string, string>;
  onRefineSearch: () => void;
  status: SessionStatus;
}) {
  const t = useTranslations("chat");
  const tCommon = useTranslations("common");
  const { data: session } = useSession();

  const [sortBy, setSortBy] = useState<ListingsSort>("deal_score_desc");
  const [showMap, setShowMap] = useState(false);

  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const query = useInfiniteQuery({
    enabled:
      Boolean(session?.accessToken) &&
      Object.keys(criteria).length > 0 &&
      (status === "confirmed" || status === "complete"),
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const response = await fetch(
        `${API_BASE_URL}/api/listings/search?${toQueryString(criteria, sortBy, pageParam)}`,
        {
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
          },
        },
      );

      if (!response.ok) {
        throw new Error("Failed to load listings");
      }

      return (await response.json()) as ListingsPage;
    },
    queryKey: ["listings", criteria, sortBy],
  });

  useEffect(() => {
    if (!sentinelRef.current || !query.hasNextPage) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void query.fetchNextPage();
        }
      },
      {
        rootMargin: "240px 0px",
      },
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [query.fetchNextPage, query.hasNextPage]);

  if (status !== "confirmed" && status !== "complete") {
    return null;
  }

  if (!session?.accessToken) {
    return (
      <div className="rounded-[32px] border border-dashed border-slate-200 bg-white/85 p-6 text-sm text-slate-600">
        <p>{t("saveHistoryPrompt")}</p>
      </div>
    );
  }

  const listings = query.data?.pages.flatMap((page) => page.items) ?? [];

  const sortButtons: Array<{ id: ListingsSort; label: string }> = [
    { id: "price_asc", label: t("sortPriceAsc") },
    { id: "price_desc", label: t("sortPriceDesc") },
    { id: "deal_score_desc", label: t("sortDealScore") },
    { id: "date_desc", label: t("sortDate") },
  ];

  return (
    <section className="space-y-5 rounded-[36px] border border-white/70 bg-white/75 p-5 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {sortButtons.map((option) => (
            <Button
              key={option.id}
              onClick={() => setSortBy(option.id)}
              variant={sortBy === option.id ? "default" : "ghost"}
            >
              {option.label}
            </Button>
          ))}
        </div>

        <Button onClick={() => setShowMap((current) => !current)} variant="outline">
          {showMap ? t("listView") : t("mapView")}
        </Button>
      </div>

      {query.isPending ? (
        <div className="rounded-[28px] bg-slate-50 p-6 text-sm text-slate-500">
          {tCommon("loading")}…
        </div>
      ) : null}

      {!query.isPending && listings.length === 0 ? (
        <div className="space-y-4 rounded-[28px] bg-slate-50 p-6 text-center">
          <p className="text-sm text-slate-500">{t("noListings")}</p>
          <div className="flex justify-center">
            <ChipSelector
              chips={[
                {
                  id: "refine-search",
                  label: t("refineSearch"),
                },
              ]}
              onSelect={() => onRefineSearch()}
            />
          </div>
        </div>
      ) : null}

      {showMap && listings.length > 0 ? (
        <MapView listings={listings} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {listings.map((listing) => (
            <ListingCard key={listing.listingId} listing={listing} />
          ))}
        </div>
      )}

      {query.hasNextPage ? <div className="h-6" ref={sentinelRef} /> : null}
    </section>
  );
}

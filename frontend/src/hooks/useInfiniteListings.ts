"use client";

import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useSession } from "next-auth/react";

import { fetchCrmBulk, fetchListings, type CrmStatus } from "@/lib/api";
import type { ListingSearchParams } from "@/lib/listing-search";
import { useCrmStore } from "@/stores/crmStore";

export function useInfiniteListings(params: ListingSearchParams) {
  const { data: session } = useSession();
  const bulkLoad = useCrmStore((state) => state.bulkLoad);

  const queryKey = useMemo(() => ["listings", params] as const, [params]);

  const query = useInfiniteQuery({
    enabled: Boolean(session?.accessToken),
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.cursor ?? undefined : undefined,
    initialPageParam: undefined as string | undefined,
    placeholderData: keepPreviousData,
    queryFn: ({ pageParam }) =>
      fetchListings(session?.accessToken, {
        ...params,
        cursor: pageParam,
        limit: 24,
      }),
    queryKey,
  });

  useEffect(() => {
    const listingIds =
      query.data?.pages.flatMap((page) => page.items.map((listing) => listing.id)) ?? [];

    if (!session?.accessToken || listingIds.length === 0) {
      return;
    }

    void fetchCrmBulk(session.accessToken, listingIds).then((entries) => {
      const statuses = Object.entries(entries).reduce<Record<string, CrmStatus>>(
        (accumulator, [listingId, entry]) => {
          accumulator[listingId] = entry.status;
          return accumulator;
        },
        {},
      );

      bulkLoad(statuses);
    });
  }, [bulkLoad, query.data?.pages, session?.accessToken]);

  return {
    ...query,
    totalCount: query.data?.pages[0]?.total ?? 0,
  };
}

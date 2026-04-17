"use client";

import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchListingDetail } from "@/lib/api";

export function useComparables(comparableIds: string[]) {
  const { data: session } = useSession();

  const queries = useQueries({
    queries: comparableIds.map((id) => ({
      queryKey: ["listing", "comparable", id],
      enabled: Boolean(session?.accessToken) && comparableIds.length > 0,
      queryFn: () => fetchListingDetail(session?.accessToken, id),
      staleTime: 120_000,
    })),
  });

  return useMemo(
    () => ({
      comparables: queries
        .map((query) => query.data)
        .filter((listing): listing is NonNullable<typeof listing> => Boolean(listing)),
      isLoading: queries.some((query) => query.isPending),
    }),
    [queries],
  );
}


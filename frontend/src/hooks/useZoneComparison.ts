"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { useState } from "react";

import {
  fetchZoneAnalytics,
  fetchZoneComparison,
  searchZoneList,
} from "@/lib/api";

export function useZoneComparison(initialZoneId: string) {
  const { data: session } = useSession();
  const [selectedIds, setSelectedIds] = useState<string[]>([initialZoneId]);
  const [query, setQuery] = useState("");

  const searchQuery = useQuery({
    queryKey: ["zones", "search", query],
    enabled: Boolean(session?.accessToken) && query.trim().length >= 2,
    queryFn: async () => {
      const result = await searchZoneList(session?.accessToken, {
        limit: 8,
        q: query.trim(),
      });

      return result.items;
    },
    staleTime: 60_000,
  });

  const comparisonQuery = useQuery({
    queryKey: ["zones", "comparison", selectedIds],
    enabled: Boolean(session?.accessToken) && selectedIds.length >= 2,
    queryFn: () => fetchZoneComparison(session?.accessToken, selectedIds),
    staleTime: 2 * 60 * 1000,
  });

  const analyticsQueries = useQueries({
    queries: selectedIds.map((id) => ({
      queryKey: ["zones", id, "analytics"],
      enabled: Boolean(session?.accessToken),
      queryFn: () => fetchZoneAnalytics(session?.accessToken, id),
      staleTime: 5 * 60 * 1000,
    })),
  });

  const analyticsMap = selectedIds.reduce<Record<string, (typeof analyticsQueries)[number]["data"]>>(
    (accumulator, id, index) => {
      accumulator[id] = analyticsQueries[index]?.data;
      return accumulator;
    },
    {},
  );

  return {
    selectedIds,
    setSelectedIds,
    addZone: (zoneId: string) =>
      setSelectedIds((current) =>
        current.includes(zoneId) ? current : [...current, zoneId].slice(0, 5),
      ),
    removeZone: (zoneId: string) =>
      setSelectedIds((current) =>
        current.length <= 1 ? current : current.filter((id) => id !== zoneId),
      ),
    comparisonData: comparisonQuery.data?.zones ?? [],
    analyticsMap,
    isLoading:
      comparisonQuery.isPending || analyticsQueries.some((comparison) => comparison.isPending),
    query,
    setQuery,
    searchResults: searchQuery.data ?? [],
  };
}

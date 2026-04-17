"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchAdminScrapingStats } from "@/lib/api";

export function useAdminScraping() {
  const { data: session } = useSession();

  const query = useQuery({
    queryKey: ["admin", "scraping"],
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchAdminScrapingStats(session?.accessToken),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  return {
    portals: query.data?.portals ?? [],
    isLoading: query.isPending,
    error: query.error ?? null,
    refetch: query.refetch,
  };
}

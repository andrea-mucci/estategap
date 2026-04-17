"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import {
  fetchZoneAnalytics,
  fetchZoneDetail,
  type ZoneDetail,
} from "@/lib/api";

export function useZoneStats(zoneId: string, initialZone?: ZoneDetail) {
  const { data: session } = useSession();
  const enabled = Boolean(session?.accessToken) && Boolean(zoneId);

  const zoneQuery = useQuery({
    queryKey: ["zones", zoneId, "detail"],
    enabled,
    initialData: initialZone,
    queryFn: () => fetchZoneDetail(session?.accessToken, zoneId),
    staleTime: 5 * 60 * 1000,
  });

  const analyticsQuery = useQuery({
    queryKey: ["zones", zoneId, "analytics"],
    enabled,
    queryFn: () => fetchZoneAnalytics(session?.accessToken, zoneId),
    staleTime: 5 * 60 * 1000,
  });

  return {
    zone: zoneQuery.data,
    analytics: analyticsQuery.data,
    isLoading: zoneQuery.isPending || analyticsQuery.isPending,
    error: zoneQuery.error ?? analyticsQuery.error ?? null,
  };
}

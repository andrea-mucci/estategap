"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchZoneAnalytics } from "@/lib/api";

export function useZoneAnalytics(zoneId: string) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["zones", zoneId, "analytics"],
    staleTime: 5 * 60 * 1000,
    enabled: Boolean(session?.accessToken) && Boolean(zoneId),
    queryFn: () => fetchZoneAnalytics(session?.accessToken, zoneId),
  });
}

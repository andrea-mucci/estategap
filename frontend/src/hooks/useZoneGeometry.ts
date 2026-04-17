"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchZoneGeometry } from "@/lib/api";

export function useZoneGeometry(zoneId: string, enabled = true) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["zones", zoneId, "geometry"],
    staleTime: 10 * 60 * 1000,
    enabled: Boolean(session?.accessToken) && Boolean(zoneId) && enabled,
    queryFn: () => fetchZoneGeometry(session?.accessToken, zoneId),
  });
}

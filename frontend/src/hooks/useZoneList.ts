"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchZoneList } from "@/lib/api";

export function useZoneList(country: string, limit = 20) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["zones", "list", country, limit],
    staleTime: 5 * 60 * 1000,
    enabled: Boolean(session?.accessToken) && Boolean(country),
    queryFn: () => fetchZoneList(session?.accessToken, country, limit),
  });
}

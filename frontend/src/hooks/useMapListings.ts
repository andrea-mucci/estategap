"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchMapListings } from "@/lib/api";

export function useMapListings(country: string, bounds: string | null) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["listings", "map", country, bounds],
    staleTime: 30_000,
    enabled: Boolean(session?.accessToken) && Boolean(country) && Boolean(bounds),
    queryFn: () => fetchMapListings(session?.accessToken, country, bounds ?? ""),
  });
}

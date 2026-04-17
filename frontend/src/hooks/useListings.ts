"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchListings, type ListingsQuery } from "@/lib/api";

export function useListings(
  params: Partial<ListingsQuery> = {},
  options?: {
    enabled?: boolean;
  },
) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["listings", params],
    enabled: Boolean(session?.accessToken) && (options?.enabled ?? true),
    queryFn: () => fetchListings(session?.accessToken, params),
  });
}

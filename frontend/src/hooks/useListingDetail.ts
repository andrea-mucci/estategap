"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchListingDetail, type ListingDetail } from "@/lib/api";
import type { ExtendedListingDetail } from "@/lib/listing-search";

export function useListingDetail(id: string, initialData?: ExtendedListingDetail) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["listing", id],
    enabled: Boolean(session?.accessToken) && Boolean(id),
    initialData: initialData as ListingDetail | undefined,
    queryFn: () => fetchListingDetail(session?.accessToken, id),
    staleTime: 120_000,
  });
}


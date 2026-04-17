"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { createApiClient, defaultListingsQuery, type ListingsQuery } from "@/lib/api";

export function useListings(params: Partial<ListingsQuery> = {}) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["listings", params],
    enabled: Boolean(session?.accessToken),
    queryFn: async () => {
      const client = createApiClient(session?.accessToken);
      const { data, error } = await client.GET("/api/v1/listings", {
        params: {
          query: {
            ...defaultListingsQuery,
            ...params,
          },
        },
      });

      if (error) {
        throw new Error(error.error || "Failed to load listings");
      }

      return data;
    },
  });
}

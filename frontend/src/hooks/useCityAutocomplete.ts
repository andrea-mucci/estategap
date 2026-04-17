"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { searchZoneList } from "@/lib/api";

export function useCityAutocomplete(term: string, country: string) {
  const { data: session } = useSession();
  const debouncedTerm = useDebouncedValue(term.trim(), 300);

  const query = useQuery({
    queryKey: ["zones", "city-autocomplete", country, debouncedTerm],
    enabled:
      Boolean(session?.accessToken) &&
      Boolean(country) &&
      debouncedTerm.length >= 2,
    queryFn: async () => {
      const response = await searchZoneList(session?.accessToken, {
        country,
        level: "city",
        limit: 10,
        q: debouncedTerm,
      });

      return response.items.map((zone) => zone.name);
    },
    staleTime: 60_000,
  });

  return {
    isLoading: query.isPending,
    suggestions: query.data ?? [],
  };
}


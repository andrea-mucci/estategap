"use client";

import { useQuery } from "@tanstack/react-query";

export function useExchangeRates() {
  const query = useQuery({
    queryKey: ["exchange-rates"],
    staleTime: 60 * 60 * 1000,
    queryFn: async () => {
      const response = await fetch("/api/exchange-rates", {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Failed to load exchange rates");
      }

      const payload = (await response.json()) as {
        rates?: Record<string, number>;
      };

      return payload.rates ?? { EUR: 1 };
    },
  });

  return {
    rates: query.data ?? { EUR: 1 },
    isLoading: query.isPending,
    error: query.error,
  };
}

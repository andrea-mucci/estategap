"use client";

import { useMemo } from "react";

import { useZoneList } from "@/hooks/useZoneList";

export function useZoneOptions(country: string, city?: string | null) {
  const query = useZoneList(country, 200);

  const zones = useMemo(() => {
    const normalizedCity = city?.trim().toLowerCase();
    if (!normalizedCity) {
      return [];
    }

    return (query.data?.items ?? []).filter((zone) => {
      const haystack = `${zone.name} ${zone.name_local ?? ""}`.toLowerCase();
      return haystack.includes(normalizedCity);
    });
  }, [city, query.data?.items]);

  return {
    isLoading: query.isPending,
    zones,
  };
}


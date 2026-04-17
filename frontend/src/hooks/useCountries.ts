"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchCountries } from "@/lib/api";

export function useCountries() {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["countries"],
    staleTime: 10 * 60 * 1000,
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchCountries(session?.accessToken),
  });
}

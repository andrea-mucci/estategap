"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchDashboardSummary } from "@/lib/api";

export function useDashboardSummary(country: string) {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["dashboard", "summary", country],
    staleTime: 60_000,
    enabled: Boolean(session?.accessToken) && Boolean(country),
    queryFn: () => fetchDashboardSummary(session?.accessToken, country),
  });
}

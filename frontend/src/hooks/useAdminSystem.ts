"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchSystemHealth } from "@/lib/api";

export function useAdminSystem() {
  const { data: session } = useSession();

  const query = useQuery({
    queryKey: ["admin", "system-health"],
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchSystemHealth(session?.accessToken),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  return {
    health: query.data ?? null,
    isLoading: query.isPending,
    error: query.error ?? null,
    refetch: query.refetch,
  };
}

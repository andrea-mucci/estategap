"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { useState } from "react";

import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { fetchAdminUsers } from "@/lib/api";

export function useAdminUsers() {
  const { data: session } = useSession();
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [tier, setTier] = useState("");
  const debouncedQuery = useDebouncedValue(query, 300);

  const result = useQuery({
    queryKey: ["admin", "users", page, debouncedQuery, tier],
    enabled: Boolean(session?.accessToken),
    queryFn: () =>
      fetchAdminUsers(session?.accessToken, {
        page,
        limit: 12,
        q: debouncedQuery,
        tier: tier || undefined,
      }),
    staleTime: 30_000,
  });

  return {
    users: result.data?.users ?? [],
    total: result.data?.total ?? 0,
    page: result.data?.page ?? page,
    limit: result.data?.limit ?? 12,
    query,
    tier,
    setPage,
    setQuery: (value: string) => {
      setPage(1);
      setQuery(value);
    },
    setTier: (value: string) => {
      setPage(1);
      setTier(value);
    },
    isLoading: result.isPending,
    error: result.error ?? null,
    refetch: result.refetch,
  };
}

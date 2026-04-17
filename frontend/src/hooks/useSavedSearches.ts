"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import {
  createSavedSearch,
  deleteSavedSearch,
  fetchSavedSearches,
  type SavedSearch,
} from "@/lib/api";
import type { ListingSearchParams } from "@/lib/listing-search";

const SAVED_SEARCHES_STORAGE_KEY = "estategap_saved_searches";
const QUERY_KEY = ["saved-searches"] as const;

function loadSavedSearchesFromStorage() {
  if (typeof window === "undefined") {
    return [] as SavedSearch[];
  }

  try {
    return JSON.parse(
      window.localStorage.getItem(SAVED_SEARCHES_STORAGE_KEY) ?? "[]",
    ) as SavedSearch[];
  } catch {
    return [];
  }
}

function persistSavedSearches(savedSearches: SavedSearch[]) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    SAVED_SEARCHES_STORAGE_KEY,
    JSON.stringify(savedSearches),
  );
}

export function useSavedSearches() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      try {
        const searches = await fetchSavedSearches(session?.accessToken);
        persistSavedSearches(searches);
        return searches;
      } catch {
        return loadSavedSearchesFromStorage();
      }
    },
  });

  const createMutation = useMutation({
    mutationFn: async ({
      filters,
      name,
    }: {
      filters: ListingSearchParams;
      name: string;
    }) => {
      try {
        return await createSavedSearch(session?.accessToken, { filters, name });
      } catch {
        const now = new Date().toISOString();
        return {
          created_at: now,
          filters,
          id: `local-${crypto.randomUUID()}`,
          name,
          updated_at: now,
        } satisfies SavedSearch;
      }
    },
    onSuccess: (savedSearch) => {
      queryClient.setQueryData<SavedSearch[]>(QUERY_KEY, (current = []) => {
        const next = [savedSearch, ...current.filter((item) => item.id !== savedSearch.id)];
        persistSavedSearches(next);
        return next;
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (savedSearchId: string) => {
      try {
        await deleteSavedSearch(session?.accessToken, savedSearchId);
      } catch {
        return;
      }
    },
    onSuccess: (_data, savedSearchId) => {
      queryClient.setQueryData<SavedSearch[]>(QUERY_KEY, (current = []) => {
        const next = current.filter((item) => item.id !== savedSearchId);
        persistSavedSearches(next);
        return next;
      });
    },
  });

  return {
    createSavedSearch: createMutation.mutateAsync,
    deleteSavedSearch: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    isSaving: createMutation.isPending,
    savedSearches: query.data ?? [],
  };
}


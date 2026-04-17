"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import {
  fetchCrmEntry,
  patchCrmStatus,
  type CrmEntry,
  type CrmStatus,
} from "@/lib/api";
import { useCrmStore } from "@/stores/crmStore";

export function useCrmStatus(listingId: string) {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const setStatus = useCrmStore((state) => state.setStatus);

  const query = useQuery({
    queryKey: ["crm", listingId],
    enabled: Boolean(session?.accessToken) && Boolean(listingId),
    queryFn: () => fetchCrmEntry(session?.accessToken, listingId),
  });

  const mutation = useMutation({
    mutationFn: (status: CrmStatus) =>
      patchCrmStatus(session?.accessToken, listingId, status),
    onMutate: async (nextStatus) => {
      await queryClient.cancelQueries({
        queryKey: ["crm", listingId],
      });

      const previousEntry = queryClient.getQueryData<CrmEntry>(["crm", listingId]);

      const optimisticEntry: CrmEntry = {
        listing_id: listingId,
        notes: previousEntry?.notes ?? "",
        status: nextStatus,
        updated_at: new Date().toISOString(),
      };

      queryClient.setQueryData(["crm", listingId], optimisticEntry);
      setStatus(listingId, nextStatus);

      return { previousEntry };
    },
    onError: (_error, _nextStatus, context) => {
      if (context?.previousEntry) {
        queryClient.setQueryData(["crm", listingId], context.previousEntry);
        setStatus(listingId, context.previousEntry.status);
      }
    },
    onSettled: (entry) => {
      if (entry) {
        queryClient.setQueryData(["crm", listingId], entry);
        setStatus(listingId, entry.status);
      }
      void queryClient.invalidateQueries({
        queryKey: ["crm", listingId],
      });
    },
  });

  return {
    crmEntry: query.data,
    isLoading: query.isPending,
    updateStatus: mutation.mutateAsync,
    updating: mutation.isPending,
  };
}


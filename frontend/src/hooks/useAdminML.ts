"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchAdminMLModels, triggerMLRetrain } from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";

export function useAdminMLModels() {
  const { data: session } = useSession();

  const query = useQuery({
    queryKey: ["admin", "ml-models"],
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchAdminMLModels(session?.accessToken),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  return {
    models: query.data?.models ?? [],
    isLoading: query.isPending,
    error: query.error ?? null,
    refetch: query.refetch,
  };
}

export function useRetrainMutation() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const pushToast = useNotificationStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (country: string) => triggerMLRetrain(session?.accessToken, country),
    onSuccess: async (data, country) => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "ml-models"] });
      pushToast({
        type: "success",
        title: `Retraining queued for ${country}`,
        description: `Job ${data.job_id} is now in the queue.`,
        durationMs: 4000,
      });
    },
    onError: (error) => {
      pushToast({
        type: "error",
        title: "Retraining failed",
        description: error instanceof Error ? error.message : "Unable to queue retraining.",
        durationMs: 4000,
      });
    },
  });
}

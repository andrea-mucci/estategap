"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { fetchAdminCountries, updateAdminCountry, type CountryConfig } from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";

export function useAdminCountries() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const pushToast = useNotificationStore((state) => state.pushToast);

  const query = useQuery({
    queryKey: ["admin", "countries"],
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchAdminCountries(session?.accessToken),
    staleTime: 30_000,
  });

  const mutation = useMutation({
    mutationFn: ({
      code,
      payload,
    }: {
      code: string;
      payload: Record<string, unknown>;
    }) => updateAdminCountry(session?.accessToken, code, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "countries"] });
      pushToast({
        type: "success",
        title: "Country updated",
        description: "The admin configuration was saved.",
        durationMs: 3000,
      });
    },
    onError: (error) => {
      pushToast({
        type: "error",
        title: "Country update failed",
        description: error instanceof Error ? error.message : "Unable to save country config.",
        durationMs: 4000,
      });
    },
  });

  return {
    countries: query.data?.countries ?? ([] as CountryConfig[]),
    isLoading: query.isPending,
    error: query.error ?? null,
    updateCountry: (code: string, payload: Record<string, unknown>) =>
      mutation.mutateAsync({ code, payload }),
    isSaving: mutation.isPending,
    refetch: query.refetch,
  };
}

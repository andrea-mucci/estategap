"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import {
  createPortfolioProperty,
  deletePortfolioProperty,
  fetchPortfolioProperties,
  updatePortfolioProperty,
  type PortfolioListResponse,
} from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";

export type PortfolioPropertyInput = {
  address: string;
  country: string;
  purchase_price: number;
  purchase_currency: string;
  purchase_date: string;
  monthly_rental_income: number;
  area_m2?: number;
  property_type: "residential" | "commercial" | "industrial" | "land";
  notes?: string;
};

const QUERY_KEY = ["portfolio"] as const;

export function usePortfolio() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const pushToast = useNotificationStore((state) => state.pushToast);

  const query = useQuery({
    queryKey: QUERY_KEY,
    enabled: Boolean(session?.accessToken),
    queryFn: () => fetchPortfolioProperties(session?.accessToken),
    staleTime: 60_000,
  });

  const createMutation = useMutation({
    mutationFn: (payload: PortfolioPropertyInput) =>
      createPortfolioProperty(session?.accessToken, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      pushToast({
        type: "success",
        title: "Property added",
        description: "The portfolio has been refreshed.",
        durationMs: 3000,
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: PortfolioPropertyInput;
    }) => updatePortfolioProperty(session?.accessToken, id, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      pushToast({
        type: "success",
        title: "Property updated",
        description: "Your portfolio changes were saved.",
        durationMs: 3000,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deletePortfolioProperty(session?.accessToken, id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEY });
      const previous = queryClient.getQueryData<PortfolioListResponse>(QUERY_KEY);

      if (previous) {
        queryClient.setQueryData<PortfolioListResponse>(QUERY_KEY, {
          ...previous,
          properties: previous.properties.filter((property) => property.id !== id),
        });
      }

      return { previous };
    },
    onError: (_error, _id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(QUERY_KEY, context.previous);
      }
    },
    onSuccess: () => {
      pushToast({
        type: "success",
        title: "Property removed",
        description: "The property has been deleted from the portfolio.",
        durationMs: 3000,
      });
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  return {
    properties: query.data?.properties ?? [],
    summary: query.data?.summary ?? null,
    isLoading: query.isPending,
    error: query.error ?? null,
    createProperty: createMutation.mutateAsync,
    updateProperty: (id: string, payload: PortfolioPropertyInput) =>
      updateMutation.mutateAsync({ id, payload }),
    deleteProperty: deleteMutation.mutateAsync,
    deletingId:
      deleteMutation.isPending && typeof deleteMutation.variables === "string"
        ? deleteMutation.variables
        : null,
    isSaving: createMutation.isPending || updateMutation.isPending,
  };
}

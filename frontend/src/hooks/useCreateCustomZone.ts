"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

import { createCustomZone, type CreateCustomZoneRequest } from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";

export function useCreateCustomZone() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const pushToast = useNotificationStore((state) => state.pushToast);

  return useMutation({
    mutationFn: async (payload: CreateCustomZoneRequest) =>
      createCustomZone(session?.accessToken, payload),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["zones", "list", variables.country],
      });

      pushToast({
        type: "success",
        title: "Zone saved successfully",
        durationMs: 4000,
      });
    },
  });
}

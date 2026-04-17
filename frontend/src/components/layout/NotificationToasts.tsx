"use client";

import { ToastViewport } from "@/components/ui/toast";
import { useNotificationStore } from "@/stores/notificationStore";

export function NotificationToasts() {
  const toasts = useNotificationStore((state) => state.toastQueue);
  const dismissToast = useNotificationStore((state) => state.dismissToast);

  return <ToastViewport onDismiss={dismissToast} toasts={toasts} />;
}

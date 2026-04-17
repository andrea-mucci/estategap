import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

export interface DealAlert {
  eventId: string;
  listingId: string;
  title: string;
  address: string;
  priceEur: number;
  areaM2: number;
  dealScore: number;
  dealTier: number;
  photoUrl?: string;
  analysisUrl?: string;
  ruleName: string;
  triggeredAt: string;
  read: boolean;
}

export interface ToastMessage {
  id: string;
  type: "alert" | "success" | "error" | "info";
  title: string;
  description?: string;
  durationMs: number;
}

export interface NotificationStore {
  alerts: DealAlert[];
  toastQueue: ToastMessage[];
  unreadCount: number;
  addAlert: (alert: DealAlert) => void;
  markRead: (eventId: string) => void;
  markAllRead: () => void;
  pushToast: (toast: Omit<ToastMessage, "id">) => void;
  dismissToast: (id: string) => void;
}

const initialState = {
  alerts: [],
  toastQueue: [],
  unreadCount: 0,
};

function createToastId() {
  return `toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function syncUnreadCount(state: Pick<NotificationStore, "alerts" | "unreadCount">) {
  state.unreadCount = state.alerts.filter((alert) => !alert.read).length;
}

export const useNotificationStore = create<NotificationStore>()(
  immer((set) => ({
    ...initialState,
    addAlert: (alert) =>
      set((state) => {
        state.alerts.unshift(alert);
        syncUnreadCount(state);
      }),
    markRead: (eventId) =>
      set((state) => {
        const alert = state.alerts.find((item) => item.eventId === eventId);
        if (alert) {
          alert.read = true;
        }
        syncUnreadCount(state);
      }),
    markAllRead: () =>
      set((state) => {
        state.alerts = state.alerts.map((alert) => ({
          ...alert,
          read: true,
        }));
        syncUnreadCount(state);
      }),
    pushToast: (toast) =>
      set((state) => {
        state.toastQueue.push({
          id: createToastId(),
          ...toast,
        });
      }),
    dismissToast: (id) =>
      set((state) => {
        state.toastQueue = state.toastQueue.filter((toast) => toast.id !== id);
      }),
  })),
);

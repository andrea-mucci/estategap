"use client";

import { useEffect } from "react";

import { cn } from "@/lib/utils";
import type { ToastMessage } from "@/stores/notificationStore";

const toneClasses: Record<ToastMessage["type"], string> = {
  alert: "border-amber-200 bg-amber-50",
  success: "border-emerald-200 bg-emerald-50",
  error: "border-rose-200 bg-rose-50",
  info: "border-slate-200 bg-white",
};

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    const timers = toasts.map((toast) =>
      window.setTimeout(() => onDismiss(toast.id), toast.durationMs),
    );

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [onDismiss, toasts]);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-3">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto rounded-[24px] border p-4 shadow-xl backdrop-blur",
            toneClasses[toast.type],
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-950">{toast.title}</p>
              {toast.description ? (
                <p className="mt-1 text-sm text-slate-600">{toast.description}</p>
              ) : null}
            </div>
            <button
              aria-label="Dismiss notification"
              className="text-sm text-slate-500"
              onClick={() => onDismiss(toast.id)}
              type="button"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

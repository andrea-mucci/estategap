"use client";

import { useEffect, useEffectEvent } from "react";
import { useSession } from "next-auth/react";

import { updateCurrentUser } from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";
import { useOnboardingStore } from "@/stores/onboardingStore";

export function useOnboarding() {
  const { data: session, status, update } = useSession();
  const pushToast = useNotificationStore((state) => state.pushToast);
  const active = useOnboardingStore((state) => state.active);
  const chatCriteria = useOnboardingStore((state) => state.chatCriteria);
  const currentStep = useOnboardingStore((state) => state.currentStep);
  const showUpgradeModal = useOnboardingStore((state) => state.showUpgradeModal);
  const advanceStep = useOnboardingStore((state) => state.advanceStep);
  const completeTour = useOnboardingStore((state) => state.completeTour);
  const setUpgradeModalOpen = useOnboardingStore((state) => state.setUpgradeModalOpen);
  const skipTour = useOnboardingStore((state) => state.skipTour);
  const startTour = useOnboardingStore((state) => state.startTour);

  useEffect(() => {
    if (status !== "authenticated") {
      return;
    }

    if (session.user.onboardingCompleted || active || showUpgradeModal) {
      return;
    }

    startTour();
  }, [active, session?.user.onboardingCompleted, showUpgradeModal, startTour, status]);

  const persistCompletion = useEffectEvent(async () => {
    if (!session?.accessToken) {
      return;
    }

    try {
      await updateCurrentUser(session.accessToken, {
        onboarding_completed: true,
      });
    } catch (error) {
      pushToast({
        type: "alert",
        title: "We couldn't save your onboarding status",
        description:
          error instanceof Error
            ? error.message
            : "Your session will continue, but the tour may reappear on another device.",
        durationMs: 4500,
      });
    }

    await update({
      onboardingCompleted: true,
    }).catch(() => undefined);
  });

  const skip = useEffectEvent(async () => {
    await persistCompletion();
    skipTour();
  });

  const complete = useEffectEvent(async () => {
    await persistCompletion();
    setUpgradeModalOpen(false);
  });

  return {
    active,
    advance: advanceStep,
    chatCriteria,
    complete,
    currentStep,
    showUpgradeModal,
    showUpgradeOptions: completeTour,
    skip,
  };
}

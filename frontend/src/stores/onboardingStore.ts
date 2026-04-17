"use client";

import { create } from "zustand";

export type OnboardingStep = "CHAT" | "ALERT" | "DASHBOARD" | "COMPLETE";

type ChatCriteria = Record<string, unknown> | null;

type OnboardingStore = {
  active: boolean;
  currentStep: OnboardingStep;
  chatCriteria: ChatCriteria;
  showUpgradeModal: boolean;
  startTour: () => void;
  advanceStep: (criteria?: Record<string, unknown> | null) => void;
  completeTour: () => void;
  skipTour: () => void;
  setUpgradeModalOpen: (open: boolean) => void;
};

const initialState = {
  active: false,
  currentStep: "CHAT" as OnboardingStep,
  chatCriteria: null as ChatCriteria,
  showUpgradeModal: false,
};

export const useOnboardingStore = create<OnboardingStore>((set) => ({
  ...initialState,
  startTour: () =>
    set({
      active: true,
      currentStep: "CHAT",
      chatCriteria: null,
      showUpgradeModal: false,
    }),
  advanceStep: (criteria) =>
    set((state) => {
      if (state.currentStep === "CHAT") {
        return {
          currentStep: "ALERT" as OnboardingStep,
          chatCriteria: criteria ?? state.chatCriteria,
        };
      }

      if (state.currentStep === "ALERT") {
        return {
          currentStep: "DASHBOARD" as OnboardingStep,
          chatCriteria: criteria ?? state.chatCriteria,
        };
      }

      return state;
    }),
  completeTour: () =>
    set((state) => ({
      active: false,
      currentStep: "COMPLETE",
      chatCriteria: state.chatCriteria,
      showUpgradeModal: true,
    })),
  skipTour: () =>
    set({
      active: false,
      currentStep: "COMPLETE",
      chatCriteria: null,
      showUpgradeModal: false,
    }),
  setUpgradeModalOpen: (open) =>
    set((state) => ({
      showUpgradeModal: open,
      active: open ? state.active : false,
    })),
}));

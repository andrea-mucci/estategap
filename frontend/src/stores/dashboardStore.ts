"use client";

import { create } from "zustand";

type MapMode = "markers" | "heatmap";

interface DashboardStore {
  selectedCountry: string;
  mapMode: MapMode;
  showZoneOverlay: boolean;
  drawingMode: boolean;
  setCountry: (country: string) => void;
  setMapMode: (mode: MapMode) => void;
  toggleZoneOverlay: () => void;
  setDrawingMode: (active: boolean) => void;
}

export const useDashboardStore = create<DashboardStore>()((set) => ({
  selectedCountry: "ES",
  mapMode: "markers",
  showZoneOverlay: false,
  drawingMode: false,
  setCountry: (country) => set(() => ({ selectedCountry: country })),
  setMapMode: (mode) => set(() => ({ mapMode: mode })),
  toggleZoneOverlay: () =>
    set((state) => ({
      showZoneOverlay: !state.showZoneOverlay,
    })),
  setDrawingMode: (active) => set(() => ({ drawingMode: active })),
}));

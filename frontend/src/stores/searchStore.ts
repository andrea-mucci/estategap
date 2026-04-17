import { create } from "zustand";

import type { SearchViewMode } from "@/lib/listing-search";

type SearchStore = {
  isSidebarOpen: boolean;
  viewMode: SearchViewMode;
  closeSidebar: () => void;
  setSidebarOpen: (value: boolean) => void;
  setViewMode: (mode: SearchViewMode) => void;
  toggleSidebar: () => void;
};

export const useSearchStore = create<SearchStore>()((set) => ({
  isSidebarOpen: false,
  viewMode: "grid",
  closeSidebar: () =>
    set(() => ({
      isSidebarOpen: false,
    })),
  setSidebarOpen: (value) =>
    set(() => ({
      isSidebarOpen: value,
    })),
  setViewMode: (mode) =>
    set(() => ({
      viewMode: mode,
    })),
  toggleSidebar: () =>
    set((state) => ({
      isSidebarOpen: !state.isSidebarOpen,
    })),
}));

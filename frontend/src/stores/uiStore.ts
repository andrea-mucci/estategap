import { create } from "zustand";

export interface UIStore {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (value: boolean) => void;
}

export const useUIStore = create<UIStore>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () =>
    set((state) => ({
      sidebarOpen: !state.sidebarOpen,
    })),
  setSidebarOpen: (value) =>
    set(() => ({
      sidebarOpen: value,
    })),
}));

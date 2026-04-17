import { create } from "zustand";

import type { CrmStatus } from "@/lib/api";

type CrmStore = {
  entries: Record<string, CrmStatus>;
  bulkLoad: (entries: Record<string, CrmStatus>) => void;
  setStatus: (listingId: string, status: CrmStatus) => void;
};

export const useCrmStore = create<CrmStore>()((set) => ({
  entries: {},
  bulkLoad: (entries) =>
    set((state) => ({
      entries: {
        ...state.entries,
        ...entries,
      },
    })),
  setStatus: (listingId, status) =>
    set((state) => ({
      entries: {
        ...state.entries,
        [listingId]: status,
      },
    })),
}));


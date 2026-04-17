"use client";

import { LayoutGrid, List } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useSearchStore } from "@/stores/searchStore";

export function ViewToggle() {
  const t = useTranslations("searchPage");
  const viewMode = useSearchStore((state) => state.viewMode);
  const setViewMode = useSearchStore((state) => state.setViewMode);

  return (
    <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white p-1">
      <Button
        aria-label={t("gridViewAriaLabel")}
        className={cn(
          "rounded-full",
          viewMode === "grid" ? "" : "bg-transparent text-slate-500 hover:bg-slate-100",
        )}
        onClick={() => setViewMode("grid")}
        size="icon"
        variant={viewMode === "grid" ? "default" : "ghost"}
      >
        <LayoutGrid className="h-4 w-4" />
      </Button>
      <Button
        aria-label={t("listViewAriaLabel")}
        className={cn(
          "rounded-full",
          viewMode === "list" ? "" : "bg-transparent text-slate-500 hover:bg-slate-100",
        )}
        onClick={() => setViewMode("list")}
        size="icon"
        variant={viewMode === "list" ? "default" : "ghost"}
      >
        <List className="h-4 w-4" />
      </Button>
    </div>
  );
}

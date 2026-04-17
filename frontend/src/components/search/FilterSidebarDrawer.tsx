"use client";

import { SlidersHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useSearchStore } from "@/stores/searchStore";

import { FilterSidebar } from "./FilterSidebar";

export function FilterSidebarDrawer({
  portals,
}: {
  portals?: string[];
}) {
  const t = useTranslations("searchPage");
  const isOpen = useSearchStore((state) => state.isSidebarOpen);
  const closeSidebar = useSearchStore((state) => state.closeSidebar);
  const setSidebarOpen = useSearchStore((state) => state.setSidebarOpen);

  return (
    <Sheet onOpenChange={setSidebarOpen} open={isOpen}>
      <SheetTrigger asChild>
        <Button className="lg:hidden" variant="outline">
          <SlidersHorizontal className="mr-2 h-4 w-4" />
          {t("filters")}
        </Button>
      </SheetTrigger>
      <SheetContent className="max-h-[90vh] overflow-auto" side="bottom">
        <div className="space-y-4">
          <FilterSidebar portals={portals} />
          <Button className="w-full" onClick={() => closeSidebar()}>
            {t("applyFilters")}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

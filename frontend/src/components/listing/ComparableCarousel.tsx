"use client";

import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { useComparables } from "@/hooks/useComparables";

import { ComparableCard } from "./ComparableCard";

export function ComparableCarousel({
  comparableIds,
}: {
  comparableIds: string[];
}) {
  const t = useTranslations("listingDetail");
  const { comparables, isLoading } = useComparables(comparableIds.slice(0, 5));

  if (comparableIds.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-xl font-semibold text-slate-950">{t("comparables")}</h2>
        <p className="text-sm text-slate-500">{t("comparablesSubtitle")}</p>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2 [scroll-snap-type:x_mandatory]">
        {isLoading
          ? Array.from({ length: 3 }).map((_, index) => (
              <Skeleton className="h-[220px] min-w-[240px]" key={index} />
            ))
          : comparables.map((comparable) => (
              <div className="[scroll-snap-align:start]" key={comparable.id}>
                <ComparableCard comparable={comparable} />
              </div>
            ))}
      </div>
    </section>
  );
}

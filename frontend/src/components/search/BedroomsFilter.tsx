"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useListingSearchParams } from "@/hooks/useSearchParams";

const options = [1, 2, 3, 4, 5];

export function BedroomsFilter() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();

  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("bedrooms")}
      </label>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Button
            className="rounded-full"
            key={option}
            onClick={() => {
              void setParams({
                min_bedrooms: params.min_bedrooms === option ? null : option,
              });
            }}
            variant={params.min_bedrooms === option ? "default" : "outline"}
          >
            {option === 5 ? "5+" : option}
          </Button>
        ))}
      </div>
    </div>
  );
}

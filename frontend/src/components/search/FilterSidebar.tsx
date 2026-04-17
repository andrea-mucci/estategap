"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useListingSearchParams } from "@/hooks/useSearchParams";

import { AreaRangeSlider } from "./AreaRangeSlider";
import { BedroomsFilter } from "./BedroomsFilter";
import { CityAutocomplete } from "./CityAutocomplete";
import { CountryFilter } from "./CountryFilter";
import { DealTierFilter } from "./DealTierFilter";
import { PortalFilter } from "./PortalFilter";
import { PriceRangeSlider } from "./PriceRangeSlider";
import { PropertyTypeFilter } from "./PropertyTypeFilter";
import { StatusFilter } from "./StatusFilter";
import { ZoneSelect } from "./ZoneSelect";

export function FilterSidebar({
  portals,
}: {
  portals?: string[];
}) {
  const t = useTranslations("searchPage");
  const { activeCount, reset } = useListingSearchParams();

  return (
    <aside className="space-y-5 rounded-[32px] border border-white/70 bg-white/90 p-5 shadow-[0_20px_50px_-32px_rgba(15,23,42,0.45)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-950">{t("filters")}</h2>
          {activeCount > 0 ? <Badge>{activeCount}</Badge> : null}
        </div>
        <Button onClick={() => reset()} size="sm" variant="ghost">
          {t("clearAll")}
        </Button>
      </div>

      <div className="space-y-5">
        <CountryFilter />
        <CityAutocomplete />
        <ZoneSelect />
        <PropertyTypeFilter />
        <PriceRangeSlider />
        <AreaRangeSlider />
        <BedroomsFilter />
        <DealTierFilter />
        <StatusFilter />
        <PortalFilter portals={portals} />
      </div>
    </aside>
  );
}

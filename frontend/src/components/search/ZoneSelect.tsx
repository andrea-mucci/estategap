"use client";

import { useTranslations } from "next-intl";

import { Select } from "@/components/ui/select";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { useZoneOptions } from "@/hooks/useZoneOptions";

export function ZoneSelect() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();
  const { isLoading, zones } = useZoneOptions(params.country, params.city);

  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("zone")}
      </label>
      <Select
        disabled={!params.city || isLoading}
        onChange={(event) => {
          void setParams({
            zone_id: event.target.value || null,
          });
        }}
        value={params.zone_id ?? ""}
      >
        <option value="">{t("allZones")}</option>
        {zones.map((zone) => (
          <option key={zone.id} value={zone.id}>
            {`${zone.name} (${zone.listing_count})`}
          </option>
        ))}
      </Select>
    </div>
  );
}

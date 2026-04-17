"use client";

import { useTranslations } from "next-intl";

import { useCountries } from "@/hooks/useCountries";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { Select } from "@/components/ui/select";

export function CountryFilter() {
  const t = useTranslations("searchPage");
  const { data, isPending } = useCountries();
  const { params, setParams } = useListingSearchParams();

  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("country")}
      </label>
      <Select
        disabled={isPending}
        onChange={(event) => {
          void setParams({
            city: null,
            country: event.target.value,
            zone_id: null,
          });
        }}
        value={params.country}
      >
        {(data?.items ?? []).map((country) => (
          <option key={country.code} value={country.code}>
            {country.name}
          </option>
        ))}
      </Select>
    </div>
  );
}

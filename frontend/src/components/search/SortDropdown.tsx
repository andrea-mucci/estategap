"use client";

import { useTranslations } from "next-intl";

import { Select } from "@/components/ui/select";
import { SORT_OPTIONS, getSortOptionLabel } from "@/lib/listing-search";
import { useListingSearchParams } from "@/hooks/useSearchParams";

export function SortDropdown() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();

  return (
    <Select
      aria-label={t("sortAriaLabel")}
      className="min-w-[180px]"
      onChange={(event) => {
        const selected = SORT_OPTIONS.find((option) => option.value === event.target.value);
        if (!selected) {
          return;
        }

        void setParams({
          sort_by: selected.sortBy,
          sort_dir: selected.sortDir,
        });
      }}
      value={`${params.sort_by}:${params.sort_dir}`}
    >
      {SORT_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {getSortOptionLabel(t, option.value)}
        </option>
      ))}
    </Select>
  );
}

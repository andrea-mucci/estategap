"use client";

import { useTranslations } from "next-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { STATUS_OPTIONS, getStatusLabel } from "@/lib/listing-search";

export function StatusFilter() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();

  return (
    <div className="space-y-3">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("status")}
      </label>
      <div className="space-y-2">
        {STATUS_OPTIONS.map((statusOption) => {
          const checked = params.status.includes(statusOption.value);

          return (
            <label
              className="flex items-center gap-3 rounded-2xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
              key={statusOption.value}
            >
              <Checkbox
                checked={checked}
                onChange={() => {
                  const nextValues = checked
                    ? params.status.filter((item) => item !== statusOption.value)
                    : [...params.status, statusOption.value];

                  void setParams({
                    status: nextValues,
                  });
                }}
              />
              {getStatusLabel(t, statusOption.value)}
            </label>
          );
        })}
      </div>
    </div>
  );
}

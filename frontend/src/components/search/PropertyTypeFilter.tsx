"use client";

import { useTranslations } from "next-intl";

import { Select } from "@/components/ui/select";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import {
  PROPERTY_CATEGORY_OPTIONS,
  PROPERTY_TYPE_OPTIONS,
  getPropertyCategoryLabel,
  getPropertyTypeLabel,
} from "@/lib/listing-search";

export function PropertyTypeFilter() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();
  const typeOptions = params.property_category
    ? PROPERTY_TYPE_OPTIONS[params.property_category]
    : [];

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          {t("category")}
        </label>
        <Select
          onChange={(event) => {
            void setParams({
              property_category: event.target.value || null,
              property_type: null,
            });
          }}
          value={params.property_category ?? ""}
        >
          <option value="">{t("allCategories")}</option>
          {PROPERTY_CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {getPropertyCategoryLabel(t, option.value)}
            </option>
          ))}
        </Select>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          {t("type")}
        </label>
        <Select
          disabled={!params.property_category}
          onChange={(event) => {
            void setParams({
              property_type: event.target.value || null,
            });
          }}
          value={params.property_type ?? ""}
        >
          <option value="">{t("allPropertyTypes")}</option>
          {typeOptions.map((option) => (
            <option key={option} value={option}>
              {getPropertyTypeLabel(t, option)}
            </option>
          ))}
        </Select>
      </div>
    </div>
  );
}

"use client";

import { useTranslations } from "next-intl";

import { useListingSearchParams } from "@/hooks/useSearchParams";

import { DualRangeField } from "./DualRangeField";

export function AreaRangeSlider() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();

  return (
    <DualRangeField
      formatValue={(value) => `${value} m²`}
      label={t("areaRange")}
      max={1_000}
      min={0}
      onCommit={([minArea, maxArea]) => {
        void setParams({
          max_area_m2: maxArea,
          min_area_m2: minArea,
        });
      }}
      step={5}
      value={[params.min_area_m2, params.max_area_m2]}
    />
  );
}

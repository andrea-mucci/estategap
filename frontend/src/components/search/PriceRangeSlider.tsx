"use client";

import { useLocale } from "next-intl";
import { useTranslations } from "next-intl";

import { useListingSearchParams } from "@/hooks/useSearchParams";
import { formatCurrency } from "@/lib/utils";

import { DualRangeField } from "./DualRangeField";

export function PriceRangeSlider() {
  const locale = useLocale();
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();

  return (
    <DualRangeField
      formatValue={(value) => formatCurrency(value, "EUR", locale)}
      label={t("priceRange")}
      max={5_000_000}
      min={0}
      onCommit={([minPrice, maxPrice]) => {
        void setParams({
          max_price_eur: maxPrice,
          min_price_eur: minPrice,
        });
      }}
      step={10_000}
      value={[params.min_price_eur, params.max_price_eur]}
    />
  );
}

"use client";

import { useTranslations } from "next-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { DEAL_TIER_OPTIONS, getDealTierDescription } from "@/lib/listing-search";

export function DealTierFilter() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();

  return (
    <div className="space-y-3">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("dealTier")}
      </label>
      <div className="space-y-2">
        {DEAL_TIER_OPTIONS.map((tier) => {
          const checked = params.deal_tier.includes(tier.value);

          return (
            <label
              className="flex items-center gap-3 rounded-2xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
              key={tier.value}
            >
              <Checkbox
                checked={checked}
                onChange={() => {
                  const nextValues = checked
                    ? params.deal_tier.filter((item) => item !== tier.value)
                    : [...params.deal_tier, tier.value];

                  void setParams({
                    deal_tier: nextValues,
                  });
                }}
              />
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tier.tone}`}>
                {tier.label}
              </span>
              <span>{getDealTierDescription(t, tier.value)}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

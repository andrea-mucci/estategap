"use client";

import { useTranslations } from "next-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { DEFAULT_PORTAL_OPTIONS } from "@/lib/listing-search";

export function PortalFilter({
  portals = DEFAULT_PORTAL_OPTIONS,
}: {
  portals?: string[];
}) {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();
  const options = portals.length > 0 ? portals : DEFAULT_PORTAL_OPTIONS;

  return (
    <div className="space-y-3">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("sourcePortal")}
      </label>
      <div className="space-y-2">
        {options.map((portal) => {
          const checked = params.source_portal.includes(portal);

          return (
            <label
              className="flex items-center gap-3 rounded-2xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
              key={portal}
            >
              <Checkbox
                checked={checked}
                onChange={() => {
                  const nextValues = checked
                    ? params.source_portal.filter((item) => item !== portal)
                    : [...params.source_portal, portal];

                  void setParams({
                    source_portal: nextValues,
                  });
                }}
              />
              {portal}
            </label>
          );
        })}
      </div>
    </div>
  );
}

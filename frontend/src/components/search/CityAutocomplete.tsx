"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useCityAutocomplete } from "@/hooks/useCityAutocomplete";
import { useListingSearchParams } from "@/hooks/useSearchParams";
import { Input } from "@/components/ui/input";

export function CityAutocomplete() {
  const t = useTranslations("searchPage");
  const { params, setParams } = useListingSearchParams();
  const [term, setTerm] = useState(params.city ?? "");
  const [open, setOpen] = useState(false);
  const { isLoading, suggestions } = useCityAutocomplete(term, params.country);

  useEffect(() => {
    setTerm(params.city ?? "");
  }, [params.city]);

  return (
    <div className="relative space-y-2">
      <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        {t("city")}
      </label>
      <Input
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 100);
        }}
        onChange={(event) => {
          setTerm(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void setParams({
              city: term || null,
              zone_id: null,
            });
            setOpen(false);
          }
        }}
        placeholder={t("cityPlaceholder")}
        value={term}
      />
      {open && term.trim().length >= 2 ? (
        <div className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-3xl border border-slate-200 bg-white p-2 shadow-xl">
          {isLoading ? (
            <p className="px-3 py-2 text-sm text-slate-500">{t("searchingCities")}</p>
          ) : suggestions.length > 0 ? (
            suggestions.map((suggestion) => (
              <button
                className="block w-full rounded-2xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                key={suggestion}
                onClick={() => {
                  setTerm(suggestion);
                  setOpen(false);
                  void setParams({
                    city: suggestion,
                    zone_id: null,
                  });
                }}
                type="button"
              >
                {suggestion}
              </button>
            ))
          ) : (
            <p className="px-3 py-2 text-sm text-slate-500">{t("noCities")}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

"use client";

import { Loader2, Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import type { ExtendedListingDetail } from "@/lib/listing-search";
import { useTranslate } from "@/hooks/useTranslate";

export function DescriptionSection({
  listing,
}: {
  listing: ExtendedListingDetail;
}) {
  const locale = useLocale();
  const t = useTranslations("listingDetail");
  const { isPending, reset, translate, translatedText } = useTranslate();
  const description = listing.description ?? "";
  const isSameLanguage =
    listing.description_language?.toLowerCase() === locale.toLowerCase();

  if (!description) {
    return (
      <section className="space-y-2" data-testid="listing-description">
        <h2 className="text-xl font-semibold text-slate-950">{t("description")}</h2>
        <p className="text-sm text-slate-500">{t("descriptionUnavailable")}</p>
      </section>
    );
  }

  const showingTranslation = Boolean(translatedText);

  return (
    <section className="space-y-3" data-testid="listing-description">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">{t("description")}</h2>
          <p className="text-sm text-slate-500">{t("descriptionSubtitle")}</p>
        </div>
        {!isSameLanguage ? (
          <Button
            data-testid="translate-button"
            onClick={async () => {
              if (showingTranslation) {
                reset();
                return;
              }

              await translate(description);
            }}
            variant="outline"
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Languages className="mr-2 h-4 w-4" />
            )}
            {showingTranslation ? t("showOriginal") : t("translate")}
          </Button>
        ) : null}
      </div>
      <div className="rounded-[28px] border border-white/70 bg-white/90 p-5 text-sm leading-7 text-slate-700">
        {translatedText ?? description}
      </div>
    </section>
  );
}

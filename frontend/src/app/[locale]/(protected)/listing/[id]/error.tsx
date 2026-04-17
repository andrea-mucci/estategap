"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";

export default function ListingError({
  error: _error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  const t = useTranslations("listingDetail");
  const tCommon = useTranslations("common");

  return (
    <div className="space-y-4 rounded-[32px] border border-rose-200 bg-rose-50 p-6">
      <div>
        <h2 className="text-2xl font-semibold text-rose-900">{t("notFoundTitle")}</h2>
        <p className="mt-2 text-sm text-rose-700">
          {t("notFoundDescription")}
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => reset()} variant="destructive">
          {tCommon("retry")}
        </Button>
        <Link href="/search">
          <Button variant="outline">{t("backToSearch")}</Button>
        </Link>
      </div>
    </div>
  );
}

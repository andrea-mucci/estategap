"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

export function ErrorDisplay({
  error,
  refetch,
}: {
  error: Error;
  refetch: () => void;
}) {
  const t = useTranslations("common");

  return (
    <div className="rounded-[28px] border border-rose-200 bg-rose-50 p-6">
      <p className="text-base font-semibold text-rose-900">{t("error")}</p>
      <p className="mt-2 text-sm text-rose-700">{error.message}</p>
      <Button className="mt-4" onClick={refetch} variant="destructive">
        {t("retry")}
      </Button>
    </div>
  );
}

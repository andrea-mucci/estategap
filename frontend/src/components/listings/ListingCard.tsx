"use client";

import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/routing";
import { cn, formatCurrency } from "@/lib/utils";

export type ListingCardProps = {
  id: string;
  title: string;
  city?: string;
  imageUrl?: string;
  price?: number | null;
  area?: number | null;
  bedrooms?: number | null;
  dealScore?: number | null;
  href?: string;
  compact?: boolean;
};

export function ListingCard({
  id,
  title,
  city,
  imageUrl,
  price,
  area,
  bedrooms,
  dealScore,
  href,
  compact = false,
}: ListingCardProps) {
  const t = useTranslations("listing");
  const locale = useLocale();

  return (
    <Card className={cn("overflow-hidden", compact ? "min-w-[260px]" : "")}>
      <div className="relative h-44 bg-slate-100">
        {imageUrl ? (
          <Image
            alt={title}
            className="object-cover"
            fill
            sizes="(max-width: 768px) 100vw, 25vw"
            src={imageUrl}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            {t("noImage")}
          </div>
        )}
      </div>
      <CardContent className="space-y-4 pt-6">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
          <p className="text-sm text-slate-500">{city}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge>{formatCurrency(price ?? undefined, "EUR", locale)}</Badge>
          {area ? <Badge>{`${t("area")}: ${area} m²`}</Badge> : null}
          {bedrooms ? <Badge>{`${t("bedrooms")}: ${bedrooms}`}</Badge> : null}
          {dealScore != null ? <Badge>{`${t("dealScore")}: ${dealScore}`}</Badge> : null}
        </div>
        <Link href={href ?? `/listing/${id}`}>
          <Button className="w-full">{t("viewDetails")}</Button>
        </Link>
      </CardContent>
    </Card>
  );
}

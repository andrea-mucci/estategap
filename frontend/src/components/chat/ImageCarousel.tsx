"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import type { CarouselImage } from "@/types/chat";

export function ImageCarousel({
  images,
  onFeedback,
}: {
  images: CarouselImage[];
  onFeedback: (listingId: string, action: "like" | "dislike") => void;
}) {
  const t = useTranslations("chat");

  return (
    <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2">
      {images.map((image) => (
        <article
          className="surface-glass min-w-[280px] snap-start rounded-[28px] border border-white/70 p-3"
          key={image.listingId}
        >
          <div className="relative h-48 overflow-hidden rounded-[22px] bg-slate-100">
            <Image
              alt={image.alt}
              className="object-cover"
              fill
              sizes="280px"
              src={image.src}
            />
          </div>

          <div className="mt-3 space-y-1">
            <p className="text-lg font-semibold text-slate-950">{image.price}</p>
            <p className="text-sm text-slate-500">{image.location}</p>
          </div>

          <div className="mt-4 flex gap-2">
            <Button
              aria-label={t("likeThis")}
              className="flex-1"
              onClick={() => onFeedback(image.listingId, "like")}
              size="sm"
              variant="outline"
            >
              {t("likeThis")}
            </Button>
            <Button
              aria-label={t("notThis")}
              className="flex-1"
              onClick={() => onFeedback(image.listingId, "dislike")}
              size="sm"
              variant="ghost"
            >
              {t("notThis")}
            </Button>
          </div>
        </article>
      ))}
    </div>
  );
}

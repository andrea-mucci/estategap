"use client";

import "yet-another-react-lightbox/styles.css";
import "yet-another-react-lightbox/plugins/thumbnails.css";

import Image from "next/image";
import { ImageIcon } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";
import Lightbox from "yet-another-react-lightbox";
import Thumbnails from "yet-another-react-lightbox/plugins/thumbnails";
import Zoom from "yet-another-react-lightbox/plugins/zoom";

import { cn } from "@/lib/utils";

export function PhotoGallery({
  photoUrls,
}: {
  photoUrls?: string[] | null;
}) {
  const t = useTranslations("listingDetail");
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const slides = (photoUrls ?? []).map((url) => ({ src: url }));

  if (slides.length === 0) {
    return (
      <div
        className="flex h-[340px] items-center justify-center rounded-[32px] bg-slate-100 text-slate-400"
        data-testid="photo-gallery"
      >
        <div className="flex items-center gap-2">
          <ImageIcon className="h-5 w-5" />
          {t("photoGalleryEmpty")}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="photo-gallery">
      <button
        className="relative block h-[380px] w-full overflow-hidden rounded-[32px] bg-slate-100"
        onClick={() => setOpen(true)}
        type="button"
      >
        <Image
          alt={t("photoAlt")}
          className="object-cover"
          fill
          priority
          sizes="(max-width: 1024px) 100vw, 1200px"
          src={slides[0].src}
        />
      </button>
      <div className="grid grid-cols-4 gap-3">
        {slides.slice(0, 4).map((slide, slideIndex) => (
          <button
            className={cn(
              "relative h-24 overflow-hidden rounded-[20px] bg-slate-100",
              slideIndex === 0 ? "ring-2 ring-teal-600" : "",
            )}
            key={slide.src}
            onClick={() => {
              setIndex(slideIndex);
              setOpen(true);
            }}
            type="button"
          >
            <Image
              alt={t("photoAltIndexed", {
                index: slideIndex + 1,
              })}
              className="object-cover"
              fill
              sizes="140px"
              src={slide.src}
            />
          </button>
        ))}
      </div>
      <Lightbox
        close={() => setOpen(false)}
        index={index}
        open={open}
        plugins={[Thumbnails, Zoom]}
        slides={slides}
      />
    </div>
  );
}

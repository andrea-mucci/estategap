"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { useTranslations } from "next-intl";

import type { PointOfInterest } from "@/lib/listing-search";

function markerEmoji(type: PointOfInterest["type"]) {
  if (type === "metro") return "🚇";
  if (type === "school") return "🏫";
  return "🌳";
}

export default function ListingMiniMap({
  latitude,
  longitude,
  pois,
}: {
  latitude?: number | null;
  longitude?: number | null;
  pois?: PointOfInterest[] | null;
}) {
  const t = useTranslations("listingDetail");
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || latitude == null || longitude == null) {
      return;
    }

    const map = new maplibregl.Map({
      center: [longitude, latitude],
      container: containerRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      zoom: 14,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    const listingMarker = document.createElement("div");
    listingMarker.className =
      "grid h-8 w-8 place-items-center rounded-full border-2 border-white bg-rose-500 text-white shadow-lg";
    listingMarker.textContent = "•";
    new maplibregl.Marker({ element: listingMarker })
      .setLngLat([longitude, latitude])
      .addTo(map);

    for (const poi of pois ?? []) {
      const element = document.createElement("div");
      element.className =
        "grid h-8 w-8 place-items-center rounded-full border border-white bg-white text-sm shadow";
      element.textContent = markerEmoji(poi.type);
      new maplibregl.Marker({ element })
        .setLngLat([poi.lng, poi.lat])
        .addTo(map);
    }

    return () => {
      map.remove();
    };
  }, [latitude, longitude, pois]);

  if (latitude == null || longitude == null) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-[28px] bg-slate-100 text-sm text-slate-500">
        {t("mapUnavailable")}
      </div>
    );
  }

  return <div className="h-[280px] overflow-hidden rounded-[28px]" ref={containerRef} />;
}

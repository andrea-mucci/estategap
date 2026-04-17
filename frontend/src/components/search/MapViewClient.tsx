"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import maplibregl from "maplibre-gl";

import { ListingCard } from "@/components/search/ListingCard";
import type { ListingCard as ListingCardModel } from "@/types/chat";

const SOURCE_ID = "listing-markers";
const LAYER_ID = "listing-points";

export default function MapViewClient({
  listings,
}: {
  listings: ListingCardModel[];
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRootRef = useRef<Root | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const initialCoordinates = listings[0]
      ? [listings[0].longitude, listings[0].latitude]
      : [2.1734, 41.3851];

    const map = new maplibregl.Map({
      center: initialCoordinates as [number, number],
      container: containerRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      zoom: listings[0] ? 11 : 4,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    return () => {
      popupRootRef.current?.unmount();
      popupRootRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [listings]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    const data = {
      type: "FeatureCollection",
      features: listings.map((listing) => ({
        geometry: {
          coordinates: [listing.longitude, listing.latitude],
          type: "Point",
        },
        properties: {
          listingId: listing.listingId,
        },
        type: "Feature",
      })),
    } as const;

    const applyLayer = () => {
      const existingSource = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(data);
      } else {
        map.addSource(SOURCE_ID, {
          data,
          type: "geojson",
        });
        map.addLayer({
          id: LAYER_ID,
          paint: {
            "circle-color": "#0f766e",
            "circle-radius": 8,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
          },
          source: SOURCE_ID,
          type: "circle",
        });
      }

      const bounds = new maplibregl.LngLatBounds();
      for (const listing of listings) {
        bounds.extend([listing.longitude, listing.latitude]);
      }

      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, {
          maxZoom: 13,
          padding: 48,
        });
      }
    };

    if (map.isStyleLoaded()) {
      applyLayer();
    } else {
      map.once("load", applyLayer);
    }

    const handleClick = (event: maplibregl.MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: [LAYER_ID],
      })[0];

      const listingId = `${feature?.properties?.listingId ?? ""}`;
      const listing = listings.find((item) => item.listingId === listingId);

      if (!listing) {
        return;
      }

      const popupContainer = document.createElement("div");
      popupRootRef.current?.unmount();
      popupRootRef.current = createRoot(popupContainer);
      popupRootRef.current.render(
        <div className="w-[260px]">
          <ListingCard compact listing={listing} />
        </div>,
      );

      new maplibregl.Popup({ closeButton: false, offset: 18 })
        .setDOMContent(popupContainer)
        .setLngLat([listing.longitude, listing.latitude])
        .addTo(map);
    };

    map.on("click", LAYER_ID, handleClick);
    return () => {
      map.off("click", LAYER_ID, handleClick);
    };
  }, [listings]);

  return (
    <div
      className="h-[420px] overflow-hidden rounded-[28px] border border-white/70"
      ref={containerRef}
    />
  );
}

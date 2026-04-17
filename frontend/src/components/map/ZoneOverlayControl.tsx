"use client";

import { useQueries } from "@tanstack/react-query";
import { useEffect, useRef, type RefObject } from "react";
import maplibregl from "maplibre-gl";
import { useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { useZoneList } from "@/hooks/useZoneList";
import { fetchZoneGeometry } from "@/lib/api";
import { useDashboardStore } from "@/stores/dashboardStore";

const ZONE_SOURCE_ID = "zone-overlays";
const ZONE_FILL_LAYER_ID = "zone-overlays-fill";
const ZONE_LINE_LAYER_ID = "zone-overlays-line";

export function ZoneOverlayControl({
  mapRef,
  country,
}: {
  mapRef: RefObject<maplibregl.Map | null>;
  country: string;
}) {
  const { data: session } = useSession();
  const showZoneOverlay = useDashboardStore((state) => state.showZoneOverlay);
  const toggleZoneOverlay = useDashboardStore((state) => state.toggleZoneOverlay);
  const tooltipRef = useRef<maplibregl.Popup | null>(null);
  const zoneListQuery = useZoneList(country);

  const zoneGeometryQueries = useQueries({
    queries: (zoneListQuery.data?.items ?? []).map((zone) => ({
      queryKey: ["zones", zone.id, "geometry"],
      staleTime: 10 * 60 * 1000,
      enabled: Boolean(session?.accessToken) && showZoneOverlay,
      queryFn: () => fetchZoneGeometry(session?.accessToken, zone.id),
    })),
  });

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) {
      return;
    }

    if (!showZoneOverlay) {
      if (map.getLayer(ZONE_FILL_LAYER_ID)) {
        map.removeLayer(ZONE_FILL_LAYER_ID);
      }
      if (map.getLayer(ZONE_LINE_LAYER_ID)) {
        map.removeLayer(ZONE_LINE_LAYER_ID);
      }
      if (map.getSource(ZONE_SOURCE_ID)) {
        map.removeSource(ZONE_SOURCE_ID);
      }
      tooltipRef.current?.remove();
      tooltipRef.current = null;
      return;
    }

    const zones = zoneListQuery.data?.items ?? [];
    const features = zones
      .map((zone, index) => {
        const geometry = zoneGeometryQueries[index]?.data;
        if (!geometry) {
          return null;
        }

        return {
          type: "Feature",
          geometry: geometry.geometry,
          properties: {
            id: zone.id,
            name: zone.name,
            median_price_m2_eur: zone.median_price_m2_eur,
            listing_count: zone.listing_count,
            deal_count: zone.deal_count,
          },
        };
      })
      .filter(Boolean);

    const geojson = {
      type: "FeatureCollection",
      features,
    };

    const existingSource = map.getSource(ZONE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (existingSource) {
      existingSource.setData(geojson as never);
    } else {
      map.addSource(ZONE_SOURCE_ID, {
        type: "geojson",
        data: geojson as never,
      });
      map.addLayer({
        id: ZONE_FILL_LAYER_ID,
        type: "fill",
        source: ZONE_SOURCE_ID,
        paint: {
          "fill-color": "#3b82f6",
          "fill-opacity": 0.15,
        },
      });
      map.addLayer({
        id: ZONE_LINE_LAYER_ID,
        type: "line",
        source: ZONE_SOURCE_ID,
        paint: {
          "line-color": "#2563eb",
          "line-width": 1.5,
        },
      });
    }

    const handleMove = (event: maplibregl.MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: [ZONE_FILL_LAYER_ID],
      })[0];

      if (!feature) {
        tooltipRef.current?.remove();
        tooltipRef.current = null;
        return;
      }

      const popup = tooltipRef.current ?? new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
      });
      tooltipRef.current = popup;
      popup
        .setLngLat(event.lngLat)
        .setHTML(
          `<div class="space-y-1">
            <strong>${feature.properties?.name ?? "Zone"}</strong><br/>
            Median €/m²: ${feature.properties?.median_price_m2_eur ?? 0}<br/>
            Listings: ${feature.properties?.listing_count ?? 0}<br/>
            Deals: ${feature.properties?.deal_count ?? 0}
          </div>`,
        )
        .addTo(map);
    };

    const handleLeave = () => {
      tooltipRef.current?.remove();
      tooltipRef.current = null;
    };

    map.on("mousemove", ZONE_FILL_LAYER_ID, handleMove);
    map.on("mouseleave", ZONE_FILL_LAYER_ID, handleLeave);

    return () => {
      map.off("mousemove", ZONE_FILL_LAYER_ID, handleMove);
      map.off("mouseleave", ZONE_FILL_LAYER_ID, handleLeave);
      tooltipRef.current?.remove();
      tooltipRef.current = null;
    };
  }, [country, mapRef, showZoneOverlay, zoneGeometryQueries, zoneListQuery.data?.items]);

  return (
    <Button onClick={() => toggleZoneOverlay()} size="sm" variant={showZoneOverlay ? "default" : "outline"}>
      Zones
    </Button>
  );
}

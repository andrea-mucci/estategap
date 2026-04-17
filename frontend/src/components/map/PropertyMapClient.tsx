"use client";

import { useEffect, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import maplibregl from "maplibre-gl";

import { DrawZoneControl } from "@/components/map/DrawZoneControl";
import { ListingPopup } from "@/components/map/ListingPopup";
import { MapLayerToggle } from "@/components/map/MapLayerToggle";
import { ZoneOverlayControl } from "@/components/map/ZoneOverlayControl";
import { useMapListings } from "@/hooks/useMapListings";
import { useDashboardStore } from "@/stores/dashboardStore";

const LISTINGS_SOURCE_ID = "dashboard-listings";
const CLUSTERS_LAYER_ID = "clusters";
const CLUSTER_COUNT_LAYER_ID = "cluster-count";
const POINTS_LAYER_ID = "unclustered-point";
const HEATMAP_LAYER_ID = "listings-heat";

const countryViews: Record<
  string,
  {
    bounds: [[number, number], [number, number]];
    center: [number, number];
    zoom: number;
  }
> = {
  ES: {
    bounds: [[-9.39, 35.94], [3.33, 43.79]],
    center: [-3.7038, 40.4168],
    zoom: 5.5,
  },
  FR: {
    bounds: [[-5.2, 41.3], [9.7, 51.1]],
    center: [2.3522, 48.8566],
    zoom: 5.2,
  },
  IT: {
    bounds: [[6.6, 36.5], [18.5, 47.1]],
    center: [12.4964, 41.9028],
    zoom: 5.4,
  },
  PT: {
    bounds: [[-9.56, 36.84], [-6.19, 42.15]],
    center: [-9.1393, 38.7223],
    zoom: 6,
  },
  GB: {
    bounds: [[-8.62, 49.87], [1.77, 60.86]],
    center: [-0.1276, 51.5072],
    zoom: 5.2,
  },
};

function ensureListingLayers(map: maplibregl.Map) {
  if (map.getSource(LISTINGS_SOURCE_ID)) {
    return;
  }

  map.addSource(LISTINGS_SOURCE_ID, {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: [],
    },
    cluster: true,
    clusterRadius: 50,
    clusterMaxZoom: 14,
  });

  map.addLayer({
    id: CLUSTERS_LAYER_ID,
    type: "circle",
    source: LISTINGS_SOURCE_ID,
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#0f766e",
      "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 50, 28],
    },
  });

  map.addLayer({
    id: CLUSTER_COUNT_LAYER_ID,
    type: "symbol",
    source: LISTINGS_SOURCE_ID,
    filter: ["has", "point_count"],
    layout: {
      "text-field": "{point_count_abbreviated}",
      "text-size": 12,
    },
    paint: {
      "text-color": "#ffffff",
    },
  });

  map.addLayer({
    id: POINTS_LAYER_ID,
    type: "circle",
    source: LISTINGS_SOURCE_ID,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "match",
        ["get", "deal_tier"],
        1,
        "#22c55e",
        2,
        "#3b82f6",
        3,
        "#9ca3af",
        4,
        "#ef4444",
        "#9ca3af",
      ],
      "circle-radius": 7,
      "circle-stroke-width": 1.5,
      "circle-stroke-color": "#ffffff",
    },
  });
}

export function PropertyMapClient({ country }: { country: string }) {
  const mapMode = useDashboardStore((state) => state.mapMode);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRootRef = useRef<Root | null>(null);
  const debounceRef = useRef<number | null>(null);
  const [bounds, setBounds] = useState<string | null>(null);
  const query = useMapListings(country, bounds);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) {
      return;
    }

    const view = countryViews[country] ?? countryViews.ES;
    const map = new maplibregl.Map({
      container,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: view.center,
      zoom: view.zoom,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      ensureListingLayers(map);
      map.fitBounds(view.bounds, {
        padding: 32,
        maxZoom: 8,
      });
      const currentBounds = map.getBounds();
      setBounds(
        `${currentBounds.getWest()},${currentBounds.getSouth()},${currentBounds.getEast()},${currentBounds.getNorth()}`,
      );
    });

    const updateBounds = () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current);
      }

      debounceRef.current = window.setTimeout(() => {
        const currentBounds = map.getBounds();
        setBounds(
          `${currentBounds.getWest()},${currentBounds.getSouth()},${currentBounds.getEast()},${currentBounds.getNorth()}`,
        );
      }, 300);
    };

    map.on("moveend", updateBounds);
    mapRef.current = map;

    return () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current);
      }
      popupRootRef.current?.unmount();
      popupRootRef.current = null;
      map.off("moveend", updateBounds);
      map.remove();
      mapRef.current = null;
    };
  }, [country]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || !map.getSource(LISTINGS_SOURCE_ID)) {
      return;
    }

    const view = countryViews[country] ?? countryViews.ES;
    map.fitBounds(view.bounds, {
      padding: 32,
      maxZoom: 8,
    });
  }, [country]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !query.data || !map.getSource(LISTINGS_SOURCE_ID)) {
      return;
    }

    const source = map.getSource(LISTINGS_SOURCE_ID) as maplibregl.GeoJSONSource;
    source.setData(query.data as never);
  }, [query.data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || !map.getSource(LISTINGS_SOURCE_ID)) {
      return;
    }

    if (mapMode === "heatmap") {
      if (!map.getLayer(HEATMAP_LAYER_ID)) {
        map.addLayer({
          id: HEATMAP_LAYER_ID,
          type: "heatmap",
          source: LISTINGS_SOURCE_ID,
          maxzoom: 16,
          paint: {
            "heatmap-weight": ["/", ["coalesce", ["get", "deal_score"], 0], 100],
            "heatmap-intensity": 1,
            "heatmap-radius": 20,
            "heatmap-opacity": 0.8,
            "heatmap-color": [
              "interpolate",
              ["linear"],
              ["heatmap-density"],
              0,
              "rgba(59,130,246,0)",
              0.2,
              "#3b82f6",
              0.4,
              "#22c55e",
              0.6,
              "#facc15",
              0.8,
              "#f97316",
              1,
              "#ef4444",
            ],
          },
        });
      }
      if (map.getLayer(CLUSTERS_LAYER_ID)) {
        map.setLayoutProperty(CLUSTERS_LAYER_ID, "visibility", "none");
      }
      if (map.getLayer(CLUSTER_COUNT_LAYER_ID)) {
        map.setLayoutProperty(CLUSTER_COUNT_LAYER_ID, "visibility", "none");
      }
      if (map.getLayer(POINTS_LAYER_ID)) {
        map.setLayoutProperty(POINTS_LAYER_ID, "visibility", "none");
      }
      return;
    }

    if (map.getLayer(HEATMAP_LAYER_ID)) {
      map.removeLayer(HEATMAP_LAYER_ID);
    }
    if (map.getLayer(CLUSTERS_LAYER_ID)) {
      map.setLayoutProperty(CLUSTERS_LAYER_ID, "visibility", "visible");
    }
    if (map.getLayer(CLUSTER_COUNT_LAYER_ID)) {
      map.setLayoutProperty(CLUSTER_COUNT_LAYER_ID, "visibility", "visible");
    }
    if (map.getLayer(POINTS_LAYER_ID)) {
      map.setLayoutProperty(POINTS_LAYER_ID, "visibility", "visible");
    }
  }, [mapMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const handleClusterClick = (event: maplibregl.MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: [CLUSTERS_LAYER_ID],
      })[0];

      const clusterId = Number(feature?.properties?.cluster_id);
      if (!Number.isFinite(clusterId)) {
        return;
      }

      const source = map.getSource(LISTINGS_SOURCE_ID) as maplibregl.GeoJSONSource & {
        getClusterExpansionZoom?: (
          cluster: number,
          callback: (error: Error | null, zoom: number) => void,
        ) => void;
      };

      source.getClusterExpansionZoom?.(clusterId, (_error, zoom) => {
        map.easeTo({
          center: (feature.geometry as { coordinates: [number, number] }).coordinates,
          zoom,
        });
      });
    };

    const handlePointClick = (event: maplibregl.MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: [POINTS_LAYER_ID],
      })[0];

      const listingId = String(feature?.properties?.id ?? "");
      const coordinates = (feature?.geometry as { coordinates?: [number, number] })?.coordinates;
      if (!listingId || !coordinates) {
        return;
      }

      const popupContainer = document.createElement("div");
      popupRootRef.current?.unmount();
      popupRootRef.current = createRoot(popupContainer);
      popupRootRef.current.render(<ListingPopup listingId={listingId} />);

      const popup = new maplibregl.Popup({ closeButton: false, offset: 18 })
        .setDOMContent(popupContainer)
        .setLngLat(coordinates)
        .addTo(map);

      popup.on("close", () => {
        popupRootRef.current?.unmount();
        popupRootRef.current = null;
      });
    };

    const bindInteractions = () => {
      if (!map.getLayer(CLUSTERS_LAYER_ID) || !map.getLayer(POINTS_LAYER_ID)) {
        return;
      }

      map.on("click", CLUSTERS_LAYER_ID, handleClusterClick);
      map.on("click", POINTS_LAYER_ID, handlePointClick);
    };

    if (map.isStyleLoaded()) {
      bindInteractions();
    } else {
      map.once("load", bindInteractions);
    }

    return () => {
      map.off("load", bindInteractions);
      map.off("click", CLUSTERS_LAYER_ID, handleClusterClick);
      map.off("click", POINTS_LAYER_ID, handlePointClick);
    };
  }, []);

  return (
    <div className="rounded-[32px] border border-white/70 bg-white/75 p-4 backdrop-blur">
      <div className="mb-3 flex flex-wrap gap-2">
        <MapLayerToggle />
        <ZoneOverlayControl mapRef={mapRef} country={country} />
        <DrawZoneControl mapRef={mapRef} country={country} />
      </div>
      <div
        className="h-screen overflow-hidden rounded-[28px] border border-white/70 md:h-[640px]"
        ref={containerRef}
      />
    </div>
  );
}

export default PropertyMapClient;

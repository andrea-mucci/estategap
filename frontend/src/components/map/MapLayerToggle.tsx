"use client";

import { Button } from "@/components/ui/button";
import { useDashboardStore } from "@/stores/dashboardStore";

export function MapLayerToggle() {
  const mapMode = useDashboardStore((state) => state.mapMode);
  const setMapMode = useDashboardStore((state) => state.setMapMode);

  return (
    <div className="inline-flex gap-2 rounded-full border border-white/70 bg-white/80 p-1">
      <Button
        onClick={() => setMapMode("markers")}
        size="sm"
        variant={mapMode === "markers" ? "default" : "outline"}
      >
        Markers
      </Button>
      <Button
        onClick={() => setMapMode("heatmap")}
        size="sm"
        variant={mapMode === "heatmap" ? "default" : "outline"}
      >
        Heatmap
      </Button>
    </div>
  );
}

"use client";

import { z } from "zod";
import { useState, type RefObject } from "react";
import type maplibregl from "maplibre-gl";
import MapboxDraw from "@mapbox/mapbox-gl-draw";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCreateCustomZone } from "@/hooks/useCreateCustomZone";
import { useDashboardStore } from "@/stores/dashboardStore";

const zoneNameSchema = z.string().trim().min(1).max(100);

function configureDrawForMapLibre() {
  const classes = (MapboxDraw as unknown as {
    constants?: {
      classes?: Record<string, string>;
    };
  }).constants?.classes;

  if (!classes) {
    return;
  }

  classes.CANVAS = "maplibregl-canvas";
  classes.CONTROL_BASE = "maplibregl-ctrl";
  classes.CONTROL_PREFIX = "maplibregl-ctrl-";
  classes.CONTROL_GROUP = "maplibregl-ctrl-group";
  classes.ATTRIBUTION = "maplibregl-ctrl-attrib";
}

export function DrawZoneControl({
  mapRef,
  country,
}: {
  mapRef: RefObject<maplibregl.Map | null>;
  country: string;
}) {
  const mutation = useCreateCustomZone();
  const drawingMode = useDashboardStore((state) => state.drawingMode);
  const setDrawingMode = useDashboardStore((state) => state.setDrawingMode);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [zoneName, setZoneName] = useState("");
  const [polygonCoordinates, setPolygonCoordinates] = useState<number[][][] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [drawInstance, setDrawInstance] = useState<MapboxDraw | null>(null);

  const cleanup = () => {
    const map = mapRef.current;
    if (map && drawInstance) {
      try {
        drawInstance.deleteAll();
        map.removeControl(drawInstance as never);
      } catch {
        // Ignore draw cleanup issues.
      }
      map.off("draw.create", handleDrawCreate as never);
    }
    setDrawInstance(null);
    setDrawingMode(false);
    setPolygonCoordinates(null);
    setZoneName("");
    setErrorMessage(null);
    setDialogOpen(false);
  };

  const handleDrawCreate = (event: {
    features?: Array<{
      geometry?: {
        type?: string;
        coordinates?: number[][][];
      };
    }>;
  }) => {
    const coordinates = event.features?.[0]?.geometry?.coordinates;
    if (!coordinates) {
      cleanup();
      return;
    }

    setPolygonCoordinates(coordinates);
    setDialogOpen(true);
  };

  const startDrawing = () => {
    const map = mapRef.current;
    if (!map || drawingMode) {
      return;
    }

    configureDrawForMapLibre();
    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: true,
        trash: true,
      },
    });

    map.addControl(draw as never, "top-left");
    map.on("draw.create", handleDrawCreate as never);
    draw.changeMode("draw_polygon");

    setDrawInstance(draw);
    setDrawingMode(true);
  };

  const saveZone = async () => {
    const parsedName = zoneNameSchema.safeParse(zoneName);
    if (!parsedName.success || !polygonCoordinates) {
      setErrorMessage("Enter a valid zone name before saving.");
      return;
    }

    setErrorMessage(null);
    try {
      await mutation.mutateAsync({
        name: parsedName.data,
        type: "custom",
        country,
        geometry: {
          type: "Polygon",
          coordinates: polygonCoordinates,
        },
      });
      cleanup();
    } catch {
      setErrorMessage("Zone could not be saved. Try again.");
    }
  };

  return (
    <>
      <Button disabled={drawingMode} onClick={startDrawing} size="sm" variant="outline">
        Draw Zone
      </Button>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            cleanup();
            return;
          }
          setDialogOpen(open);
        }}
      >
        <DialogContent>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-semibold text-slate-950">Save custom zone</h3>
              <p className="mt-1 text-sm text-slate-600">
                Name the polygon before saving it to your zone list.
              </p>
            </div>

            <Input
              maxLength={100}
              onChange={(event) => setZoneName(event.target.value)}
              placeholder="My investment area"
              value={zoneName}
            />

            {errorMessage ? <p className="text-sm text-rose-600">{errorMessage}</p> : null}

            <div className="flex justify-end gap-2">
              <Button onClick={cleanup} variant="outline">
                Cancel
              </Button>
              <Button disabled={mutation.isPending} onClick={() => void saveZone()}>
                {mutation.isPending ? "Saving..." : "Save zone"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

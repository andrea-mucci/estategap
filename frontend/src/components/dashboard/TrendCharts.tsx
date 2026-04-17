"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DealScoreHistogram } from "@/components/dashboard/DealScoreHistogram";
import { PriceZoneChart } from "@/components/dashboard/PriceZoneChart";
import { VolumeChart } from "@/components/dashboard/VolumeChart";

export function TrendCharts({ country }: { country: string }) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Price per m²</CardTitle>
        </CardHeader>
        <CardContent>
          <PriceZoneChart country={country} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Monthly volume</CardTitle>
        </CardHeader>
        <CardContent>
          <VolumeChart country={country} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Deal score spread</CardTitle>
        </CardHeader>
        <CardContent>
          <DealScoreHistogram country={country} />
        </CardContent>
      </Card>
    </div>
  );
}

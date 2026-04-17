"use client";

import dynamic from "next/dynamic";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const PriceZoneChart = dynamic(
  () => import("@/components/dashboard/PriceZoneChart").then((module) => module.PriceZoneChart),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

const VolumeChart = dynamic(
  () => import("@/components/dashboard/VolumeChart").then((module) => module.VolumeChart),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

const DealScoreHistogram = dynamic(
  () =>
    import("@/components/dashboard/DealScoreHistogram").then(
      (module) => module.DealScoreHistogram,
    ),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

function ChartPlaceholder() {
  return (
    <div className="grid h-[280px] place-items-center rounded-3xl bg-slate-50 text-sm text-slate-500">
      Loading chart…
    </div>
  );
}

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

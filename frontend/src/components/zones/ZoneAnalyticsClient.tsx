"use client";

import dynamic from "next/dynamic";
import { useLocale } from "next-intl";
import { useSession } from "next-auth/react";

import { ZoneMetricsBar } from "@/components/zones/ZoneMetricsBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { useExchangeRates } from "@/hooks/useExchangeRates";
import { useZoneComparison } from "@/hooks/useZoneComparison";
import { useZoneStats } from "@/hooks/useZoneStats";
import type { ZoneDetail } from "@/lib/api";

const ZonePriceTrendChart = dynamic(
  () => import("@/components/zones/ZonePriceTrendChart").then((module) => module.ZonePriceTrendChart),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

const ZoneVolumeChart = dynamic(
  () => import("@/components/zones/ZoneVolumeChart").then((module) => module.ZoneVolumeChart),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

const ZonePriceHistogram = dynamic(
  () => import("@/components/zones/ZonePriceHistogram").then((module) => module.ZonePriceHistogram),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

const ZoneComparisonTool = dynamic(
  () => import("@/components/zones/ZoneComparisonTool").then((module) => module.ZoneComparisonTool),
  {
    loading: () => <ChartPlaceholder />,
    ssr: false,
  },
);

function ChartPlaceholder() {
  return (
    <div className="grid min-h-[260px] place-items-center rounded-3xl bg-slate-50 text-sm text-slate-500">
      Loading chart…
    </div>
  );
}

export function ZoneAnalyticsClient({
  initialZone,
  zoneId,
}: {
  initialZone: ZoneDetail;
  zoneId: string;
}) {
  const locale = useLocale();
  const { data: session } = useSession();
  const preferredCurrency = session?.user.preferredCurrency ?? "EUR";
  const { rates, isLoading: isRatesLoading } = useExchangeRates();
  const { zone, analytics, isLoading, error } = useZoneStats(zoneId, initialZone);
  const comparison = useZoneComparison(zoneId);

  if (isLoading || isRatesLoading) {
    return <LoadingSkeleton rows={6} />;
  }

  if (error || !zone || !analytics) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Zone analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">
            Zone analytics are unavailable right now.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
          {zone.country}
        </p>
        <h1 className="text-3xl font-semibold text-slate-950">{zone.name}</h1>
        <p className="text-sm text-slate-500">
          Normalized to {preferredCurrency} for the current session ({locale.toUpperCase()}).
        </p>
      </div>

      <ZoneMetricsBar
        analytics={analytics}
        preferredCurrency={preferredCurrency}
        rates={rates}
      />

      <div className="grid gap-6 xl:grid-cols-2">
        <ZonePriceTrendChart
          months={analytics.months}
          preferredCurrency={preferredCurrency}
          rates={rates}
        />
        <ZoneVolumeChart months={analytics.months} />
      </div>

      <ZonePriceHistogram
        preferredCurrency={preferredCurrency}
        rates={rates}
        zoneId={zoneId}
      />

      <ZoneComparisonTool
        comparison={comparison}
        preferredCurrency={preferredCurrency}
        rates={rates}
      />
    </section>
  );
}

"use client";

import { useQueries } from "@tanstack/react-query";
import { format } from "date-fns";
import { useSession } from "next-auth/react";
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useZoneList } from "@/hooks/useZoneList";
import { fetchZoneAnalytics } from "@/lib/api";

const palette = ["#0f766e", "#1d4ed8", "#dc2626", "#7c3aed", "#d97706"];

export function PriceZoneChart({ country }: { country: string }) {
  const { data: session } = useSession();
  const [hiddenSeries, setHiddenSeries] = useState<string[]>([]);
  const zonesQuery = useZoneList(country);

  const zones = [...(zonesQuery.data?.items ?? [])]
    .sort((left, right) => right.listing_count - left.listing_count)
    .slice(0, 5)
    .map((zone, index) => ({
      ...zone,
      seriesKey: `zone_${index}`,
    }));

  const analyticsQueries = useQueries({
    queries: zones.map((zone) => ({
      queryKey: ["zones", zone.id, "analytics"],
      staleTime: 5 * 60 * 1000,
      enabled: Boolean(session?.accessToken),
      queryFn: () => fetchZoneAnalytics(session?.accessToken, zone.id),
    })),
  });

  if (zonesQuery.isPending || analyticsQueries.some((query) => query.isPending)) {
    return <Skeleton className="h-[280px] w-full" />;
  }

  if (zonesQuery.isError || analyticsQueries.some((query) => query.isError)) {
    return <p className="h-[280px] text-sm text-slate-500">Trend data is unavailable.</p>;
  }

  if (zones.length === 0) {
    return <p className="h-[280px] text-sm text-slate-500">No trend data available yet.</p>;
  }

  const byMonth = new Map<string, Record<string, number | string>>();

  zones.forEach((zone, index) => {
    const analytics = analyticsQueries[index]?.data;
    analytics?.months.forEach((month) => {
      const existing = byMonth.get(month.month) ?? {
        label: format(new Date(month.month), "MMM yy"),
        rawMonth: month.month,
      };
      existing[zone.seriesKey] = month.median_price_m2_eur;
      byMonth.set(month.month, existing);
    });
  });

  const data = [...byMonth.values()].sort((left, right) =>
    String(left.rawMonth).localeCompare(String(right.rawMonth)),
  );

  return (
    <div className="space-y-4">
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="label" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={54} />
            <Tooltip
              formatter={(value: number) => `${Math.round(Number(value)).toLocaleString()} €/m²`}
            />
            <Legend
              onClick={(entry: { dataKey?: string | number }) => {
                const key = typeof entry.dataKey === "string" ? entry.dataKey : "";
                if (!key) {
                  return;
                }
                setHiddenSeries((current) =>
                  current.includes(key)
                    ? current.filter((item) => item !== key)
                    : [...current, key],
                );
              }}
            />
            {zones.map((zone, index) => (
              <Line
                key={zone.id}
                type="monotone"
                dataKey={zone.seriesKey}
                name={zone.name}
                stroke={palette[index % palette.length]}
                strokeWidth={2}
                dot={false}
                hide={hiddenSeries.includes(zone.seriesKey)}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

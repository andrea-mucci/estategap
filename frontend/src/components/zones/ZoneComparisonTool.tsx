"use client";

import { format } from "date-fns";
import { useLocale } from "next-intl";
import { useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { convertFromEUR, formatCurrency } from "@/lib/currency";
import type { useZoneComparison } from "@/hooks/useZoneComparison";
import { useNotificationStore } from "@/stores/notificationStore";

const palette = ["#0f766e", "#1d4ed8", "#dc2626", "#7c3aed", "#d97706"];

function formatPercent(value: number, locale: string) {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 1,
  }).format(value);
}

export function ZoneComparisonTool({
  comparison,
  rates,
  preferredCurrency,
}: {
  comparison: ReturnType<typeof useZoneComparison>;
  rates: Record<string, number>;
  preferredCurrency: string;
}) {
  const locale = useLocale();
  const pushToast = useNotificationStore((state) => state.pushToast);
  const [hiddenIds, setHiddenIds] = useState<string[]>([]);

  const chartRows = new Map<string, Record<string, number | string>>();
  comparison.comparisonData.forEach((zone, index) => {
    const analytics = comparison.analyticsMap[zone.id];
    analytics?.months.forEach((month) => {
      const existing = chartRows.get(month.month) ?? {
        label: format(new Date(month.month), "MMM yy"),
      };

      existing[zone.id] = convertFromEUR(
        month.median_price_m2_eur,
        preferredCurrency,
        rates,
      );
      existing[`name_${zone.id}`] = zone.name;
      existing[`color_${zone.id}`] = palette[index % palette.length];
      chartRows.set(month.month, existing);
    });
  });

  const chartData = [...chartRows.entries()]
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([, value]) => value);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compare zones</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <Input
            onChange={(event) => comparison.setQuery(event.target.value)}
            placeholder="Search zones across countries"
            value={comparison.query}
          />
          {comparison.searchResults.length > 0 ? (
            <div className="grid gap-2">
              {comparison.searchResults.map((zone) => (
                <button
                  className="rounded-2xl border border-slate-200 px-4 py-3 text-left text-sm transition hover:border-teal-300 hover:bg-teal-50"
                  key={zone.id}
                  onClick={() => {
                    if (
                      comparison.selectedIds.length >= 5 &&
                      !comparison.selectedIds.includes(zone.id)
                    ) {
                      pushToast({
                        type: "info",
                        title: "Comparison limit reached",
                        description: "You can compare up to 5 zones at once.",
                        durationMs: 3000,
                      });
                      return;
                    }

                    comparison.addZone(zone.id);
                    comparison.setQuery("");
                  }}
                  type="button"
                >
                  <div className="font-medium text-slate-950">{zone.name}</div>
                  <div className="text-slate-500">{zone.country}</div>
                </button>
              ))}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {comparison.comparisonData.map((zone) => (
              <Badge className="gap-2" key={zone.id}>
                {zone.name}
                <button
                  className="text-xs"
                  onClick={() => comparison.removeZone(zone.id)}
                  type="button"
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        </div>

        {comparison.comparisonData.length >= 2 ? (
          <>
            <div className="overflow-x-auto rounded-3xl border border-slate-200">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Zone</th>
                    <th className="px-4 py-3 font-medium">Country</th>
                    <th className="px-4 py-3 font-medium">Median price / m²</th>
                    <th className="px-4 py-3 font-medium">Volume</th>
                    <th className="px-4 py-3 font-medium">Inventory</th>
                    <th className="px-4 py-3 font-medium">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.comparisonData.map((zone) => (
                    <tr className="border-t border-slate-200" key={zone.id}>
                      <td className="px-4 py-3 font-medium text-slate-950">{zone.name}</td>
                      <td className="px-4 py-3">{zone.country}</td>
                      <td className="px-4 py-3">
                        {formatCurrency(
                          convertFromEUR(zone.median_price_m2_eur, preferredCurrency, rates),
                          preferredCurrency,
                          locale,
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {zone.deal_count.toLocaleString(locale)}
                      </td>
                      <td className="px-4 py-3">
                        {zone.listing_count.toLocaleString(locale)}
                      </td>
                      <td className="px-4 py-3">
                        {`${zone.price_trend_pct && zone.price_trend_pct >= 0 ? "+" : ""}${formatPercent(zone.price_trend_pct ?? 0, locale)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {comparison.comparisonData.map((zone, index) => (
                  <Button
                    key={zone.id}
                    onClick={() =>
                      setHiddenIds((current) =>
                        current.includes(zone.id)
                          ? current.filter((item) => item !== zone.id)
                          : [...current, zone.id],
                      )
                    }
                    variant={hiddenIds.includes(zone.id) ? "outline" : "default"}
                  >
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: palette[index % palette.length] }}
                    />
                    {zone.name}
                  </Button>
                ))}
              </div>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <XAxis dataKey="label" tickLine={false} axisLine={false} />
                    <YAxis tickLine={false} axisLine={false} width={64} />
                    <Tooltip
                      formatter={(value: number) =>
                        formatCurrency(value, preferredCurrency, locale)
                      }
                    />
                    {comparison.comparisonData.map((zone, index) => (
                      <Line
                        dataKey={zone.id}
                        dot={false}
                        hide={hiddenIds.includes(zone.id)}
                        key={zone.id}
                        name={zone.name}
                        stroke={palette[index % palette.length]}
                        strokeWidth={3}
                        type="monotone"
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        ) : (
          <p className="text-sm text-slate-500">
            Add at least one more zone to unlock the comparison table and overlay chart.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

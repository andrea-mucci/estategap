"use client";

import { format } from "date-fns";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ZoneAnalytics } from "@/lib/api";

export function ZoneVolumeChart({
  months,
}: {
  months: ZoneAnalytics["months"];
}) {
  const data = months.map((month) => {
    const ratio =
      month.listing_count > 0 ? month.deal_count / month.listing_count : 0;

    return {
      label: format(new Date(month.month), "MMM yy"),
      listingCount: month.listing_count,
      fill:
        ratio >= 0.5
          ? "#0f766e"
          : ratio >= 0.25
            ? "#1d4ed8"
            : "#94a3b8",
    };
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Volume</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={44} />
              <Tooltip formatter={(value: number) => `${Number(value)} listings`} />
              <Bar dataKey="listingCount" radius={[8, 8, 0, 0]}>
                {data.map((entry) => (
                  <Cell key={entry.label} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

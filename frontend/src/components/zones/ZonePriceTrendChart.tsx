"use client";

import { format } from "date-fns";
import { useLocale } from "next-intl";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { convertFromEUR, formatCurrency } from "@/lib/currency";
import type { ZoneAnalytics } from "@/lib/api";

export function ZonePriceTrendChart({
  months,
  rates,
  preferredCurrency,
}: {
  months: ZoneAnalytics["months"];
  rates: Record<string, number>;
  preferredCurrency: string;
}) {
  const locale = useLocale();
  const data = months.map((month) => ({
    label: format(new Date(month.month), "MMM yy"),
    month: month.month,
    price: convertFromEUR(month.median_price_m2_eur, preferredCurrency, rates),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Price trend</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={64} />
              <Tooltip
                formatter={(value: number) =>
                  formatCurrency(value, preferredCurrency, locale)
                }
                labelFormatter={(label) => `${label}`}
              />
              <Line
                dataKey="price"
                dot={false}
                stroke="#0f766e"
                strokeWidth={3}
                type="monotone"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

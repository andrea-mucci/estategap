"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { useSession } from "next-auth/react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { convertFromEUR, formatCurrency } from "@/lib/currency";
import { fetchZonePriceDistribution } from "@/lib/api";

function buildHistogram(prices: number[]) {
  if (prices.length < 5) {
    return [];
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const binsCount = Math.max(1, Math.ceil(Math.log2(prices.length)) + 1);
  const width = max === min ? 1 : (max - min) / binsCount;

  const bins = Array.from({ length: binsCount }, (_, index) => ({
    from: min + index * width,
    to: index === binsCount - 1 ? max : min + (index + 1) * width,
    count: 0,
  }));

  prices.forEach((price) => {
    const rawIndex = width === 0 ? 0 : Math.floor((price - min) / width);
    const index = Math.min(bins.length - 1, Math.max(0, rawIndex));
    bins[index].count += 1;
  });

  return bins.map((bin) => ({
    label: `${Math.round(bin.from).toLocaleString()}-${Math.round(bin.to).toLocaleString()}`,
    count: bin.count,
    midpoint: (bin.from + bin.to) / 2,
  }));
}

export function ZonePriceHistogram({
  zoneId,
  rates,
  preferredCurrency,
}: {
  zoneId: string;
  rates: Record<string, number>;
  preferredCurrency: string;
}) {
  const locale = useLocale();
  const { data: session } = useSession();
  const query = useQuery({
    queryKey: ["zones", zoneId, "price-distribution"],
    enabled: Boolean(session?.accessToken) && Boolean(zoneId),
    queryFn: () => fetchZonePriceDistribution(session?.accessToken, zoneId),
    staleTime: 5 * 60 * 1000,
  });

  if (query.isPending) {
    return <Skeleton className="h-[360px] w-full" />;
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Price distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">Histogram data is unavailable.</p>
        </CardContent>
      </Card>
    );
  }

  const convertedPrices = query.data.prices_eur.map((price) =>
    convertFromEUR(price, preferredCurrency, rates),
  );
  const data = buildHistogram(convertedPrices);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Price distribution</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-sm text-amber-700">
            Fewer than 5 active listings were available for this histogram.
          </p>
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <XAxis dataKey="label" hide />
                <YAxis tickLine={false} axisLine={false} width={40} />
                <Tooltip
                  formatter={(value: number) => `${Number(value)} listings`}
                  labelFormatter={(_label, payload) => {
                    const midpoint = payload?.[0]?.payload?.midpoint as number | undefined;
                    return midpoint === undefined
                      ? "Price range"
                      : formatCurrency(midpoint, preferredCurrency, locale);
                  }}
                />
                <Bar dataKey="count" fill="#1d4ed8" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

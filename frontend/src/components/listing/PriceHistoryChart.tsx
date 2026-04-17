"use client";

import { format } from "date-fns";
import { useTranslations } from "next-intl";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExtendedListingDetail } from "@/lib/listing-search";
import { getPriceHistoryPoints } from "@/lib/listing-search";
import { formatCurrency } from "@/lib/utils";

function PriceHistoryChartInner({
  listing,
  locale,
}: {
  listing: ExtendedListingDetail;
  locale: string;
}) {
  const t = useTranslations("listingDetail");
  const data = getPriceHistoryPoints(listing.price_history);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("priceHistory")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">{t("noPriceHistory")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("priceHistory")}</CardTitle>
      </CardHeader>
      <CardContent className="h-[320px]">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart data={data}>
            <XAxis
              dataKey="date"
              tickFormatter={(value) => format(new Date(value), "MMM yy")}
            />
            <YAxis tickFormatter={(value) => `€${Math.round(value / 1000)}k`} />
            <Tooltip
              formatter={(value) =>
                formatCurrency(typeof value === "number" ? value : Number(value), "EUR", locale)
              }
              labelFormatter={(value) => format(new Date(value), "PPP")}
            />
            <Line
              dataKey="price"
              dot={data.length === 1 ? { r: 5 } : { r: 3 }}
              stroke="#0f766e"
              strokeWidth={3}
              type="monotone"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function PriceHistoryChart({
  listing,
  locale,
}: {
  listing: ExtendedListingDetail;
  locale: string;
}) {
  return (
    <ErrorBoundary
      fallback={
        <Card>
          <CardContent className="py-8 text-sm text-slate-500">
            <PriceHistoryChartFallback />
          </CardContent>
        </Card>
      }
    >
      <PriceHistoryChartInner listing={listing} locale={locale} />
    </ErrorBoundary>
  );
}

function PriceHistoryChartFallback() {
  const t = useTranslations("listingDetail");

  return t("chartUnavailable");
}

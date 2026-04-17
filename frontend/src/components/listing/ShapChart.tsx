"use client";

import { useTranslations } from "next-intl";
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getShapLabel, type ExtendedListingDetail } from "@/lib/listing-search";

type TranslationFn = (key: string) => string;

function buildChartData(
  listing: ExtendedListingDetail,
  t: TranslationFn,
) {
  return Object.entries(listing.shap_features ?? {})
    .map(([key, value]) => ({
      label: getShapLabel(t, key),
      value: typeof value === "number" ? value : Number(value ?? 0),
    }))
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
    .slice(0, 5);
}

function ShapChartInner({ listing }: { listing: ExtendedListingDetail }) {
  const t = useTranslations("listingDetail");
  const data = buildChartData(listing, t);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("whyThisScore")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">{t("noAnalysis")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("whyThisScore")}</CardTitle>
      </CardHeader>
      <CardContent className="h-[320px]">
        <ResponsiveContainer height="100%" width="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 24, right: 8 }}>
            <XAxis type="number" />
            <YAxis dataKey="label" type="category" width={120} />
            <Tooltip />
            <ReferenceLine stroke="#94a3b8" x={0} />
            <Bar dataKey="value">
              {data.map((entry) => (
                <Cell
                  fill={entry.value >= 0 ? "#22c55e" : "#ef4444"}
                  key={entry.label}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function ShapChart({ listing }: { listing: ExtendedListingDetail }) {
  return (
    <ErrorBoundary
      fallback={
        <Card>
          <CardContent className="py-8 text-sm text-slate-500">
            <ShapChartFallback />
          </CardContent>
        </Card>
      }
    >
      <ShapChartInner listing={listing} />
    </ErrorBoundary>
  );
}

function ShapChartFallback() {
  const t = useTranslations("listingDetail");

  return t("chartUnavailable");
}

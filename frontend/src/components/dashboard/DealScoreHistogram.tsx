"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useSession } from "next-auth/react";

import { Skeleton } from "@/components/ui/skeleton";
import { fetchListings } from "@/lib/api";

function buildBins(scores: number[]) {
  const bins = Array.from({ length: 10 }, (_, index) => ({
    label: index === 9 ? "90-100" : `${index * 10}-${index * 10 + 9}`,
    count: 0,
  }));

  scores.forEach((score) => {
    const normalized = Math.max(0, Math.min(100, Math.floor(score)));
    const index = Math.min(9, Math.floor(normalized / 10));
    bins[index].count += 1;
  });

  return bins;
}

export function DealScoreHistogram({ country }: { country: string }) {
  const { data: session } = useSession();
  const query = useQuery({
    queryKey: ["dashboard", "histogram", country],
    enabled: Boolean(session?.accessToken) && Boolean(country),
    queryFn: async () => {
      const firstPage = await fetchListings(session?.accessToken, {
        country,
        limit: 100,
        sort_by: "deal_score",
        sort_dir: "desc",
      });

      const secondPage = firstPage.cursor
        ? await fetchListings(session?.accessToken, {
            country,
            limit: 100,
            sort_by: "deal_score",
            sort_dir: "desc",
            cursor: firstPage.cursor,
          })
        : null;

      const items = [...firstPage.items, ...(secondPage?.items ?? [])];
      const scores = items
        .map((item) => item.deal_score)
        .filter((value): value is number => typeof value === "number");

      return {
        basedOn: items.length,
        approximate: firstPage.total > items.length,
        bins: buildBins(scores),
      };
    },
  });

  if (query.isPending) {
    return <Skeleton className="h-[280px] w-full" />;
  }

  if (query.isError || !query.data) {
    return <p className="h-[280px] text-sm text-slate-500">Deal score data is unavailable.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="h-[248px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={query.data.bins}>
            <XAxis dataKey="label" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={36} />
            <Tooltip formatter={(value: number) => `${Number(value)} listings`} />
            <Bar dataKey="count" fill="#0f766e" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {query.data.approximate ? (
        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
          Based on top {query.data.basedOn} listings
        </p>
      ) : null}
    </div>
  );
}

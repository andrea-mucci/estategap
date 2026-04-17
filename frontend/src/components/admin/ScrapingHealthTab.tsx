"use client";

import { formatDistanceToNow } from "date-fns";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminScraping } from "@/hooks/useAdminScraping";

function statusClasses(status: string) {
  switch (status) {
    case "error":
      return "bg-rose-50 text-rose-700";
    case "paused":
      return "bg-amber-50 text-amber-700";
    default:
      return "bg-emerald-50 text-emerald-700";
  }
}

export function ScrapingHealthTab() {
  const scraping = useAdminScraping();

  if (scraping.error) {
    return (
      <ErrorDisplay
        error={scraping.error instanceof Error ? scraping.error : new Error("Unable to load scraping stats.")}
        refetch={() => {
          void scraping.refetch();
        }}
      />
    );
  }

  const groups = scraping.portals.reduce<Record<string, typeof scraping.portals>>((accumulator, portal) => {
    accumulator[portal.country] = accumulator[portal.country] ?? [];
    accumulator[portal.country].push(portal);
    return accumulator;
  }, {});

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scraping health</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {scraping.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton className="h-14 w-full" key={index} />
            ))}
          </div>
        ) : (
          Object.entries(groups).map(([country, portals]) => (
            <div key={country}>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {country}
              </h3>
              <div className="overflow-x-auto rounded-[24px] border border-slate-200">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Portal</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Last scrape</th>
                      <th className="px-4 py-3 font-medium">Listings (24h)</th>
                      <th className="px-4 py-3 font-medium">Success rate</th>
                      <th className="px-4 py-3 font-medium">Blocks (24h)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portals.map((portal) => (
                      <tr className="border-t border-slate-200" key={portal.portal_id}>
                        <td className="px-4 py-3 font-medium text-slate-950">{portal.portal_name}</td>
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusClasses(portal.status)}`}>
                            {portal.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {portal.last_scrape_at
                            ? formatDistanceToNow(new Date(portal.last_scrape_at), { addSuffix: true })
                            : "No heartbeat"}
                        </td>
                        <td className="px-4 py-3">{portal.listings_24h.toLocaleString()}</td>
                        <td className="px-4 py-3">{(portal.success_rate * 100).toFixed(1)}%</td>
                        <td className="px-4 py-3">{portal.blocks_24h.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

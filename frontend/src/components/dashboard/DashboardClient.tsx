"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

import { CountryTabs } from "@/components/dashboard/CountryTabs";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { TrendCharts } from "@/components/dashboard/TrendCharts";
import { PropertyMap } from "@/components/map/PropertyMap";
import { useDashboardStore } from "@/stores/dashboardStore";

export function DashboardClient({ country }: { country: string }) {
  const searchParams = useSearchParams();
  const currentCountry = (searchParams.get("country") ?? country).toUpperCase();
  const setCountry = useDashboardStore((state) => state.setCountry);

  useEffect(() => {
    setCountry(currentCountry);
  }, [currentCountry, setCountry]);

  return (
    <section className="space-y-6">
      <CountryTabs country={currentCountry} />
      <SummaryCards country={currentCountry} />
      <TrendCharts country={currentCountry} />
      <PropertyMap country={currentCountry} />
    </section>
  );
}

"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { useCountries } from "@/hooks/useCountries";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/stores/dashboardStore";

function maxCountriesForTier(tier?: string) {
  switch (tier) {
    case "free":
      return 1;
    case "basic":
      return 3;
    default:
      return Number.POSITIVE_INFINITY;
  }
}

export function CountryTabs({ country }: { country: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const query = useCountries();
  const setCountry = useDashboardStore((state) => state.setCountry);

  const maxCountries = maxCountriesForTier(session?.user.subscriptionTier);
  const countries = (query.data?.items ?? []).slice(0, maxCountries);

  const activeCountry = (searchParams.get("country") ?? country).toUpperCase();

  return (
    <div className="overflow-x-auto pb-2">
      <div className="inline-flex min-w-full gap-2 rounded-full border border-white/70 bg-white/70 p-2">
        {countries.map((item) => (
          <Button
            className={cn(
              "shrink-0",
              activeCountry === item.code ? "" : "border-transparent bg-transparent",
            )}
            key={item.code}
            onClick={() => {
              const params = new URLSearchParams(searchParams.toString());
              params.set("country", item.code);
              setCountry(item.code);
              router.push(`${pathname}?${params.toString()}`);
            }}
            variant={activeCountry === item.code ? "default" : "outline"}
          >
            <span className="font-semibold">{item.code}</span>
            <span className="ml-2 text-xs uppercase tracking-[0.18em] opacity-70">
              {item.name}
            </span>
          </Button>
        ))}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAdminCountries } from "@/hooks/useAdminCountries";
import type { CountryConfig, PortalConfig } from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";

function toDraftValue(config: PortalConfig["config"]) {
  return JSON.stringify(config ?? {}, null, 2);
}

export function CountriesTab() {
  const countries = useAdminCountries();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const pushToast = useNotificationStore((state) => state.pushToast);

  if (countries.error) {
    return (
      <ErrorDisplay
        error={
          countries.error instanceof Error
            ? countries.error
            : new Error("Unable to load countries.")
        }
        refetch={() => {
          void countries.refetch();
        }}
      />
    );
  }

  async function updateCountry(country: CountryConfig, portals: PortalConfig[], enabled = country.enabled) {
    await countries.updateCountry(country.code, {
      enabled,
      portals,
    });
  }

  return (
    <div className="space-y-4">
      {countries.isLoading ? (
        Array.from({ length: 3 }).map((_, index) => (
          <Skeleton className="h-40 w-full" key={index} />
        ))
      ) : (
        countries.countries.map((country) => (
          <Card key={country.code}>
            <CardHeader className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <CardTitle>{country.name}</CardTitle>
                <p className="text-sm text-slate-500">
                  {country.code} · {country.portals.length} portals configured
                </p>
              </div>
              <Button
                onClick={async () => {
                  const nextEnabled = !country.enabled;
                  const confirmed = window.confirm(
                    `${nextEnabled ? "Enable" : "Disable"} ${country.name}?`,
                  );
                  if (!confirmed) {
                    return;
                  }
                  await updateCountry(country, country.portals, nextEnabled);
                }}
                variant={country.enabled ? "default" : "outline"}
              >
                {country.enabled ? "Enabled" : "Disabled"}
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {country.portals.map((portal) => (
                <div className="rounded-[24px] border border-slate-200 p-4" key={portal.id}>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="font-semibold text-slate-950">{portal.name}</p>
                      <p className="text-sm text-slate-500">
                        Status: {portal.enabled ? "enabled" : "disabled"}
                      </p>
                    </div>
                    <Button
                      onClick={async () => {
                        await updateCountry(
                          country,
                          country.portals.map((item) =>
                            item.id === portal.id
                              ? {
                                  ...item,
                                  enabled: !item.enabled,
                                }
                              : item,
                          ),
                        );
                      }}
                      size="sm"
                      variant={portal.enabled ? "secondary" : "outline"}
                    >
                      {portal.enabled ? "Disable portal" : "Enable portal"}
                    </Button>
                  </div>

                  <details className="mt-4 rounded-[20px] bg-slate-50 p-4">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700">
                      Edit JSON config
                    </summary>
                    <div className="mt-4 space-y-3">
                      <Textarea
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [portal.id]: event.target.value,
                          }))
                        }
                        value={drafts[portal.id] ?? toDraftValue(portal.config)}
                      />
                      <Button
                        disabled={countries.isSaving}
                        onClick={async () => {
                          try {
                            const nextConfig = JSON.parse(
                              drafts[portal.id] ?? toDraftValue(portal.config),
                            ) as Record<string, unknown>;
                            await updateCountry(
                              country,
                              country.portals.map((item) =>
                                item.id === portal.id
                                  ? {
                                      ...item,
                                      config: nextConfig,
                                    }
                                  : item,
                              ),
                            );
                          } catch (error) {
                            pushToast({
                              type: "error",
                              title: "Invalid JSON",
                              description:
                                error instanceof Error ? error.message : "Portal config must be valid JSON.",
                              durationMs: 4000,
                            });
                          }
                        }}
                        size="sm"
                      >
                        Save portal config
                      </Button>
                    </div>
                  </details>
                </div>
              ))}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}

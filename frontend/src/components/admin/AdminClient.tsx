"use client";

import { useSession } from "next-auth/react";
import { useState } from "react";

import { CountriesTab } from "@/components/admin/CountriesTab";
import { MLModelsTab } from "@/components/admin/MLModelsTab";
import { ScrapingHealthTab } from "@/components/admin/ScrapingHealthTab";
import { SystemHealthTab } from "@/components/admin/SystemHealthTab";
import { UsersTab } from "@/components/admin/UsersTab";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const tabs = [
  {
    id: "scraping",
    label: "Scraping health",
  },
  {
    id: "ml",
    label: "ML models",
  },
  {
    id: "users",
    label: "Users",
  },
  {
    id: "countries",
    label: "Countries",
  },
  {
    id: "system",
    label: "System",
  },
] as const;

type TabId = (typeof tabs)[number]["id"];

export function AdminClient() {
  const { data: session } = useSession();
  const [activeTab, setActiveTab] = useState<TabId>("scraping");
  const [mountedTabs, setMountedTabs] = useState<Record<TabId, boolean>>({
    scraping: true,
    ml: false,
    users: false,
    countries: false,
    system: false,
  });

  if (session?.user.role !== "admin") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Admin access required</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">
            This area is only available to EstateGap administrators.
          </p>
        </CardContent>
      </Card>
    );
  }

  function activateTab(tabId: TabId) {
    setActiveTab(tabId);
    setMountedTabs((current) => ({
      ...current,
      [tabId]: true,
    }));
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
          Operations console
        </p>
        <h1 className="text-3xl font-semibold text-slate-950">Admin panel</h1>
        <p className="max-w-2xl text-sm text-slate-500">
          Monitor scrapers, inspect model quality, manage countries, and review platform health.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <Button
            key={tab.id}
            onClick={() => activateTab(tab.id)}
            variant={activeTab === tab.id ? "default" : "outline"}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      <div className={activeTab === "scraping" ? "block" : "hidden"}>
        {mountedTabs.scraping ? <ScrapingHealthTab /> : null}
      </div>
      <div className={activeTab === "ml" ? "block" : "hidden"}>
        {mountedTabs.ml ? <MLModelsTab /> : null}
      </div>
      <div className={activeTab === "users" ? "block" : "hidden"}>
        {mountedTabs.users ? <UsersTab /> : null}
      </div>
      <div className={activeTab === "countries" ? "block" : "hidden"}>
        {mountedTabs.countries ? <CountriesTab /> : null}
      </div>
      <div className={activeTab === "system" ? "block" : "hidden"}>
        {mountedTabs.system ? <SystemHealthTab /> : null}
      </div>
    </section>
  );
}

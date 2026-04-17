"use client";

import type { ComponentType } from "react";
import { Bell, Briefcase, ChartNoAxesColumn, Home, Map, Search, Shield } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import { Link, usePathname } from "@/i18n/routing";

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  requiresAdmin?: boolean;
};

function SidebarNav() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const { data: session } = useSession();
  const closeSidebar = useUIStore((state) => state.setSidebarOpen);

  const navItems: NavItem[] = [
    { href: "/home", label: t("home"), icon: Home },
    { href: "/search", label: t("search"), icon: Search },
    { href: "/dashboard", label: t("dashboard"), icon: ChartNoAxesColumn },
    { href: "/zones", label: t("zones"), icon: Map },
    { href: "/alerts", label: t("alerts"), icon: Bell },
    { href: "/portfolio", label: t("portfolio"), icon: Briefcase },
    { href: "/admin", label: t("admin"), icon: Shield, requiresAdmin: true },
  ];

  return (
    <nav className="space-y-2">
      {navItems
        .filter((item) => !item.requiresAdmin || session?.user.role === "admin")
        .map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              className={cn(
                "flex items-center gap-3 rounded-3xl px-4 py-3 text-sm font-medium transition",
                isActive
                  ? "bg-slate-950 text-white shadow-lg"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
              )}
              href={item.href}
              key={item.href}
              onClick={() => closeSidebar(false)}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
    </nav>
  );
}

export function Sidebar() {
  const locale = useLocale();
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);

  return (
    <>
      <aside className="hidden border-r border-white/60 bg-white/80 px-6 py-8 lg:block">
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            {locale.toUpperCase()}
          </p>
          <h2 className="mt-3 text-lg font-semibold text-slate-950">Workspace</h2>
        </div>
        <SidebarNav />
      </aside>
      <Sheet onOpenChange={setSidebarOpen} open={sidebarOpen}>
        <SheetContent className="space-y-8" side="left">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              {locale.toUpperCase()}
            </p>
            <h2 className="mt-3 text-lg font-semibold text-slate-950">Workspace</h2>
          </div>
          <SidebarNav />
          <Button className="w-full" onClick={() => setSidebarOpen(false)} variant="outline">
            Close
          </Button>
        </SheetContent>
      </Sheet>
    </>
  );
}

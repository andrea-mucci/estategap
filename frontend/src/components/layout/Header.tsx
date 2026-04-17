"use client";

import { Bell, Menu } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { UserMenu } from "@/components/layout/UserMenu";
import { Link } from "@/i18n/routing";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUIStore } from "@/stores/uiStore";

export function Header() {
  const tMeta = useTranslations("meta");
  const tCommon = useTranslations("common");
  const unreadCount = useNotificationStore((state) => state.unreadCount);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);

  return (
    <header className="surface-glass sticky top-0 z-40 flex h-20 items-center justify-between border-b border-white/60 px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <Button
          aria-label={tCommon("menu")}
          className="lg:hidden"
          onClick={toggleSidebar}
          data-testid="sidebar-toggle"
          size="icon"
          variant="outline"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <Link className="space-y-1" href="/home">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-teal-700">
            EstateGap
          </p>
          <p className="text-lg font-semibold text-slate-950">{tMeta("appName")}</p>
        </Link>
      </div>
      <div className="flex items-center gap-3">
        <LanguageSwitcher />
        <Link href="/alerts">
          <Button aria-label={tCommon("notifications")} className="relative" size="icon" variant="outline">
            <Bell className="h-5 w-5" />
            {unreadCount > 0 ? (
              <Badge className="absolute -right-2 -top-2 h-6 min-w-6 justify-center rounded-full px-2 py-1">
                {unreadCount}
              </Badge>
            ) : null}
          </Button>
        </Link>
        <UserMenu />
      </div>
    </header>
  );
}

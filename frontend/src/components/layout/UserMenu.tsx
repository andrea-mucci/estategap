"use client";

import { LogOut, Settings, UserCircle2 } from "lucide-react";
import { useLocale } from "next-intl";
import { signOut, useSession } from "next-auth/react";
import { useState, useTransition } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select } from "@/components/ui/select";
import { updateCurrentUser } from "@/lib/api";
import { SUPPORTED_CURRENCIES } from "@/lib/currency";
import { useNotificationStore } from "@/stores/notificationStore";

export function UserMenu() {
  const locale = useLocale();
  const { data: session, update } = useSession();
  const [optimisticCurrency, setOptimisticCurrency] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const pushToast = useNotificationStore((state) => state.pushToast);

  if (!session?.user) {
    return null;
  }

  const initials =
    session.user.name
      ?.split(" ")
      .map((chunk) => chunk[0])
      .join("")
      .slice(0, 2) || session.user.email.slice(0, 2);
  const preferredCurrency = optimisticCurrency ?? session.user.preferredCurrency;

  function handleCurrencyChange(currency: string) {
    if (!session.accessToken || currency === preferredCurrency) {
      return;
    }

    setOptimisticCurrency(currency);
    startTransition(() => {
      void (async () => {
        try {
          await updateCurrentUser(session.accessToken, {
            preferred_currency: currency,
          });
          await update({
            preferredCurrency: currency,
          });
          pushToast({
            type: "success",
            title: "Currency updated",
            description: `All money values will use ${currency} in the current session.`,
            durationMs: 3000,
          });
          setOptimisticCurrency(null);
        } catch (error) {
          setOptimisticCurrency(null);
          pushToast({
            type: "error",
            title: "Currency update failed",
            description:
              error instanceof Error ? error.message : "Unable to update preferred currency.",
            durationMs: 4000,
          });
        }
      })();
    });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="gap-3 rounded-full px-2" variant="ghost">
          <Avatar className="h-10 w-10">
            {session.user.image ? (
              <AvatarImage alt={session.user.name ?? session.user.email} src={session.user.image} />
            ) : null}
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="hidden text-left sm:block">
            <p className="text-sm font-semibold text-slate-900">
              {session.user.name || session.user.email}
            </p>
            <p className="text-xs text-slate-500">{session.user.email}</p>
          </div>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel>
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-950">
              {session.user.name || session.user.email}
            </p>
            <p className="text-xs normal-case tracking-normal text-slate-500">
              {session.user.email}
            </p>
            <Badge>{session.user.subscriptionTier}</Badge>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem>
          <UserCircle2 className="h-4 w-4" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Settings className="h-4 w-4" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <div className="px-3 py-2">
          <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Currency
          </label>
          <Select
            disabled={isPending}
            onChange={(event) => handleCurrencyChange(event.target.value)}
            value={preferredCurrency}
          >
            {SUPPORTED_CURRENCIES.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </Select>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => signOut({ callbackUrl: `/${locale}/login` })}>
          <LogOut className="h-4 w-4" />
          Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

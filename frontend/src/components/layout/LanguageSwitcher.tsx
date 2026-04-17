"use client";

import { Globe } from "lucide-react";
import { useLocale } from "next-intl";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  localeLabels,
  locales,
  usePathname,
  useRouter,
  type AppLocale,
} from "@/i18n/routing";

export function LanguageSwitcher() {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          aria-label="Switch language"
          className="gap-2"
          disabled={isPending}
          variant="outline"
        >
          <Globe className="h-4 w-4" />
          <span>{locale.toUpperCase()}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Languages</DropdownMenuLabel>
        {locales.map((nextLocale) => (
          <DropdownMenuItem
            key={nextLocale}
            onSelect={() =>
              startTransition(() => {
                router.replace(pathname, { locale: nextLocale });
              })
            }
          >
            <span className="w-8 font-semibold uppercase text-slate-400">
              {nextLocale}
            </span>
            <span>{localeLabels[nextLocale]}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

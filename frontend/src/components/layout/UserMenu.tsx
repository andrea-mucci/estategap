"use client";

import { LogOut, Settings, UserCircle2 } from "lucide-react";
import { useLocale } from "next-intl";
import { signOut, useSession } from "next-auth/react";

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

export function UserMenu() {
  const locale = useLocale();
  const { data: session } = useSession();

  if (!session?.user) {
    return null;
  }

  const initials =
    session.user.name
      ?.split(" ")
      .map((chunk) => chunk[0])
      .join("")
      .slice(0, 2) || session.user.email.slice(0, 2);

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
        <DropdownMenuItem onSelect={() => signOut({ callbackUrl: `/${locale}/login` })}>
          <LogOut className="h-4 w-4" />
          Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

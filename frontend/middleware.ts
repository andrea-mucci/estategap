import createIntlMiddleware from "next-intl/middleware";
import { NextResponse } from "next/server";

import { auth } from "@/auth";
import { hasLocale } from "next-intl";
import { routing } from "@/i18n/routing";

const handleI18nRouting = createIntlMiddleware(routing);
const protectedSegments = new Set([
  "dashboard",
  "home",
  "search",
  "zones",
  "alerts",
  "portfolio",
  "admin",
  "listing",
]);

export default auth((request) => {
  const response = handleI18nRouting(request);
  const { pathname } = request.nextUrl;
  const segments = pathname.split("/").filter(Boolean);
  const locale = segments[0];
  const firstSegment = segments[1];

  if (!locale || !hasLocale(routing.locales, locale)) {
    return response;
  }

  if (request.auth && pathname === `/${locale}`) {
    return NextResponse.redirect(new URL(`/${locale}/home`, request.url));
  }

  if (!firstSegment || !protectedSegments.has(firstSegment)) {
    return response;
  }

  if (request.auth) {
    if (firstSegment === "admin" && request.auth.user?.role !== "admin") {
      const dashboardUrl = new URL(`/${locale}/dashboard`, request.url);
      dashboardUrl.searchParams.set("error", "forbidden");
      return NextResponse.redirect(dashboardUrl);
    }

    return response;
  }

  const loginUrl = new URL(`/${locale}/login`, request.url);
  loginUrl.searchParams.set("callbackUrl", pathname);
  return NextResponse.redirect(loginUrl);
});

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};

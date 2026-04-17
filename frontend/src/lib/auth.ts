import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { defaultLocale } from "@/i18n/routing";

export async function requireSession(locale = defaultLocale) {
  const session = await auth();

  if (!session) {
    redirect(`/${locale}/login`);
  }

  return session;
}

export async function getAccessToken(locale = defaultLocale) {
  const session = await requireSession(locale);
  return session.accessToken;
}

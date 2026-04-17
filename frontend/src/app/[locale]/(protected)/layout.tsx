import type { ReactNode } from "react";

import { MainLayout } from "@/components/layout/MainLayout";
import { requireSession } from "@/lib/auth";
import { WSProvider } from "@/providers/WSProvider";

export default async function ProtectedLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  await requireSession(locale);

  return (
    <WSProvider>
      <MainLayout>{children}</MainLayout>
    </WSProvider>
  );
}

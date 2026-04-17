import type { ReactNode } from "react";

import OnboardingTour from "@/components/onboarding/OnboardingTour";
import UpgradeModal from "@/components/onboarding/UpgradeModal";
import { MainLayout } from "@/components/layout/MainLayout";
import { requireSession } from "@/lib/auth";

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
    <MainLayout>
      {children}
      <OnboardingTour />
      <UpgradeModal />
    </MainLayout>
  );
}

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { AdminClient } from "@/components/admin/AdminClient";
import { requireSession } from "@/lib/auth";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });

  return {
    title: t("admin"),
  };
}

export default async function AdminPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const session = await requireSession(locale);

  if (session.user.role !== "admin") {
    notFound();
  }

  const t = await getTranslations({ locale, namespace: "nav" });

  return (
    <section className="space-y-6">
      <h1 className="text-3xl font-semibold text-slate-950">{t("admin")}</h1>
      <AdminClient />
    </section>
  );
}

import type { Metadata } from "next";

import FAQ from "@/components/landing/FAQ";
import Features from "@/components/landing/Features";
import Hero from "@/components/landing/Hero";
import LandingFooter from "@/components/landing/LandingFooter";
import LandingNav from "@/components/landing/LandingNav";
import Pricing from "@/components/landing/Pricing";
import Testimonials from "@/components/landing/Testimonials";
import { routing } from "@/i18n/routing";
import { getMarketingMessages } from "@/lib/marketing-content";

export const dynamic = "force-static";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const messages = getMarketingMessages(locale);

  return {
    title: messages.landing.meta.title,
    description: messages.landing.meta.description,
    alternates: {
      canonical: `/${locale}`,
      languages: Object.fromEntries(routing.locales.map((item) => [item, `/${item}`])),
    },
    openGraph: {
      title: messages.landing.meta.title,
      description: messages.landing.meta.description,
      locale,
      type: "website",
      url: `https://estategap.com/${locale}`,
    },
  };
}

export default function LocaleLandingPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(15,118,110,0.16),transparent_30%),radial-gradient(circle_at_top_right,rgba(249,115,22,0.12),transparent_24%),linear-gradient(180deg,#fcfdfd_0%,#eef4f8_100%)]">
      <LandingNav />
      <main>
        <Hero />
        <Features id="features" />
        <Pricing />
        <Testimonials />
        <FAQ />
      </main>
      <LandingFooter />
    </div>
  );
}

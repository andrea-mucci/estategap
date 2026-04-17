import { getLocale, getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/routing";
import { PRICING_TIERS } from "@/lib/pricing";

export default async function Pricing() {
  const locale = await getLocale();
  const t = await getTranslations("landing.pricing");
  const tiers = t.raw("tiers") as Record<
    string,
    {
      audience: string;
      cta: string;
      features: string[];
      name: string;
    }
  >;

  const formatter = new Intl.NumberFormat(locale, {
    currency: "EUR",
    maximumFractionDigits: 0,
    style: "currency",
  });

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24" id="pricing">
      <div className="max-w-3xl space-y-4">
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-700">
          {t("eyebrow")}
        </p>
        <h2 className="text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
          {t("title")}
        </h2>
        <p className="text-lg leading-8 text-slate-600">{t("subtitle")}</p>
      </div>

      <div className="mt-12 grid gap-4 lg:hidden">
        {PRICING_TIERS.map((tier) => {
          const copy = tiers[tier.id];
          const price = tier.price == null ? t("contactLabel") : `${formatter.format(tier.price)}${t("monthSuffix")}`;

          return (
            <article
              className={tier.highlighted ? "rounded-[32px] border border-teal-300 bg-teal-50 p-6 shadow-[0_30px_80px_-44px_rgba(13,148,136,0.45)]" : "rounded-[32px] border border-white/70 bg-white/90 p-6 shadow-[0_20px_60px_-38px_rgba(15,23,42,0.45)]"}
              key={tier.id}
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-2xl font-semibold text-slate-950">{copy.name}</h3>
                  <p className="mt-2 text-sm text-slate-500">{copy.audience}</p>
                </div>
                <p className="text-right text-2xl font-semibold text-slate-950">{price}</p>
              </div>
              <ul className="mt-5 space-y-3 text-sm text-slate-600">
                {copy.features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
              <Button asChild className="mt-6 w-full" variant={tier.highlighted ? "default" : "outline"}>
                <Link href={tier.ctaHref}>{copy.cta}</Link>
              </Button>
            </article>
          );
        })}
      </div>

      <div className="mt-12 hidden lg:block">
        <Table className="overflow-hidden rounded-[36px] shadow-[0_28px_90px_-52px_rgba(15,23,42,0.55)]">
          <TableHeader>
            <TableRow className="[&>*]:border-slate-950">
              <TableHead className="rounded-tl-[36px]">{t("planLabel")}</TableHead>
              <TableHead>{t("priceLabel")}</TableHead>
              <TableHead>{t("bestForLabel")}</TableHead>
              <TableHead>{t("includesLabel")}</TableHead>
              <TableHead className="rounded-tr-[36px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {PRICING_TIERS.map((tier, index) => {
              const copy = tiers[tier.id];
              const price = tier.price == null ? t("contactLabel") : `${formatter.format(tier.price)}${t("monthSuffix")}`;

              return (
                <TableRow
                  className={tier.highlighted ? "bg-teal-50 ring-2 ring-inset ring-teal-600" : index % 2 === 0 ? "bg-white/95" : "bg-slate-50/80"}
                  key={tier.id}
                >
                  <TableCell className="text-base font-semibold text-slate-950">{copy.name}</TableCell>
                  <TableCell className="text-base font-semibold text-slate-950">{price}</TableCell>
                  <TableCell>{copy.audience}</TableCell>
                  <TableCell>
                    <ul className="space-y-2">
                      {copy.features.map((feature) => (
                        <li key={feature}>{feature}</li>
                      ))}
                    </ul>
                  </TableCell>
                  <TableCell>
                    <Button asChild variant={tier.highlighted ? "default" : "outline"}>
                      <Link href={tier.ctaHref}>{copy.cta}</Link>
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

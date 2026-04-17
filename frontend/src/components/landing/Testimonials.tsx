import { getTranslations } from "next-intl/server";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function Testimonials() {
  const t = await getTranslations("landing.testimonials");
  const items = t.raw("items") as Array<{
    author: string;
    company: string;
    quote: string;
    role: string;
  }>;

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
      <div className="max-w-3xl space-y-4">
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-700">
          {t("eyebrow")}
        </p>
        <h2 className="text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
          {t("title")}
        </h2>
      </div>

      <div className="mt-12 grid gap-5 lg:grid-cols-3">
        {items.map((item) => (
          <Card className="h-full" key={item.author}>
            <CardHeader>
              <CardTitle className="text-xl leading-8 text-slate-900">
                “{item.quote}”
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-semibold text-slate-950">{item.author}</p>
              <p className="mt-1 text-sm text-slate-500">
                {item.role} · {item.company}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

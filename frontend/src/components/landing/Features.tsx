import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";

function Illustration({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="rounded-[32px] border border-white/70 bg-white/80 p-6 shadow-[0_30px_80px_-48px_rgba(15,23,42,0.55)]">
      <svg aria-hidden className="h-48 w-full text-slate-950" viewBox="0 0 320 200">
        {children}
      </svg>
    </div>
  );
}

const illustrations = [
  <Illustration key="search">
    <rect fill="#0f172a" height="120" opacity="0.08" rx="24" width="280" x="20" y="28" />
    <rect fill="#0f766e" height="18" opacity="0.12" rx="9" width="180" x="40" y="52" />
    <rect fill="#0f172a" height="16" opacity="0.08" rx="8" width="120" x="40" y="84" />
    <rect fill="#0f172a" height="16" opacity="0.08" rx="8" width="150" x="40" y="110" />
    <circle cx="246" cy="86" fill="#14b8a6" r="34" />
    <path d="M240 83h14M247 76v14" stroke="#ffffff" strokeLinecap="round" strokeWidth="6" />
  </Illustration>,
  <Illustration key="score">
    <rect fill="#0f172a" height="132" opacity="0.08" rx="28" width="280" x="20" y="24" />
    <path d="M48 136L98 90L144 112L208 58L272 76" fill="none" stroke="#0f766e" strokeLinecap="round" strokeWidth="10" />
    <circle cx="208" cy="58" fill="#f97316" r="11" />
    <circle cx="98" cy="90" fill="#0f766e" r="11" />
  </Illustration>,
  <Illustration key="alerts">
    <rect fill="#0f172a" height="132" opacity="0.08" rx="28" width="280" x="20" y="24" />
    <rect fill="#0f766e" height="54" opacity="0.16" rx="18" width="120" x="44" y="48" />
    <rect fill="#0f172a" height="16" opacity="0.08" rx="8" width="86" x="188" y="52" />
    <rect fill="#0f172a" height="16" opacity="0.08" rx="8" width="74" x="188" y="82" />
    <circle cx="132" cy="132" fill="#f97316" r="18" />
    <path d="M132 118v18M123 127h18" stroke="#fff" strokeLinecap="round" strokeWidth="5" />
  </Illustration>,
  <Illustration key="dashboard">
    <rect fill="#0f172a" height="132" opacity="0.08" rx="28" width="280" x="20" y="24" />
    <rect fill="#0f766e" height="84" opacity="0.18" rx="20" width="80" x="40" y="48" />
    <rect fill="#0f172a" height="32" opacity="0.08" rx="16" width="132" x="142" y="48" />
    <rect fill="#0f172a" height="32" opacity="0.08" rx="16" width="132" x="142" y="100" />
  </Illustration>,
];

export default async function Features({ id }: { id?: string }) {
  const t = await getTranslations("landing.features");
  const items = t.raw("items") as Array<{
    body: string;
    metric: string;
    title: string;
  }>;

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24" id={id}>
      <div className="max-w-3xl space-y-4">
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-700">
          {t("eyebrow")}
        </p>
        <h2 className="text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
          {t("title")}
        </h2>
        <p className="text-lg leading-8 text-slate-600">{t("intro")}</p>
      </div>

      <div className="mt-14 space-y-8">
        {items.map((item, index) => (
          <div
            className="grid items-center gap-8 rounded-[36px] border border-white/70 bg-white/55 p-6 shadow-[0_30px_90px_-55px_rgba(15,23,42,0.55)] lg:grid-cols-2 lg:p-8"
            key={item.title}
          >
            <div className={index % 2 === 1 ? "lg:order-2" : undefined}>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-400">
                {item.metric}
              </p>
              <h3 className="mt-4 text-3xl font-semibold text-slate-950">{item.title}</h3>
              <p className="mt-4 text-base leading-8 text-slate-600">{item.body}</p>
            </div>
            <div className={index % 2 === 1 ? "lg:order-1" : undefined}>{illustrations[index]}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

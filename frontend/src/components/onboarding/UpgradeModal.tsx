"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/routing";
import { useOnboardingStore } from "@/stores/onboardingStore";
import { useOnboarding } from "@/hooks/useOnboarding";

export default function UpgradeModal() {
  const router = useRouter();
  const t = useTranslations("onboarding");
  const tiers = t.raw("upgrade.tiers") as Record<
    "free" | "pro" | "global",
    {
      features: string[];
      name: string;
    }
  >;
  const { complete, showUpgradeModal } = useOnboarding();
  const setUpgradeModalOpen = useOnboardingStore((state) => state.setUpgradeModalOpen);
  const [isPending, setIsPending] = useState(false);

  async function finishAndMaybeNavigate(target?: string) {
    if (isPending) {
      return;
    }

    setIsPending(true);
    await complete();
    if (target) {
      router.push(target);
    }
    setIsPending(false);
  }

  return (
    <Dialog
      onOpenChange={(open) => {
        if (!open) {
          void finishAndMaybeNavigate();
          return;
        }

        setUpgradeModalOpen(true);
      }}
      open={showUpgradeModal}
    >
      <DialogContent className="max-w-4xl rounded-[36px] border border-white/80 bg-slate-950 p-0 text-white">
        <div className="overflow-hidden rounded-[36px]">
          <div className="bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.2),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(251,146,60,0.16),transparent_26%)] px-8 py-8">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-teal-200">
              EstateGap
            </p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight">{t("upgrade.title")}</h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">{t("upgrade.body")}</p>
          </div>

          <div className="grid gap-4 px-6 py-6 lg:grid-cols-3 lg:px-8">
            {(["free", "pro", "global"] as const).map((tier) => (
              <article
                className={tier === "pro" ? "rounded-[28px] border border-teal-400/40 bg-teal-400/10 p-5" : "rounded-[28px] border border-white/10 bg-white/5 p-5"}
                key={tier}
              >
                <h3 className="text-xl font-semibold">{tiers[tier].name}</h3>
                <ul className="mt-4 space-y-3 text-sm text-slate-300">
                  {tiers[tier].features.map((feature) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>

          <div className="flex flex-col gap-3 px-6 pb-8 lg:flex-row lg:justify-end lg:px-8">
            <Button disabled={isPending} onClick={() => void finishAndMaybeNavigate()} variant="outline">
              {t("upgrade.stayFree")}
            </Button>
            <Button disabled={isPending} onClick={() => void finishAndMaybeNavigate("/register?tier=pro")}>
              {t("upgrade.upgradePro")}
            </Button>
            <Button disabled={isPending} onClick={() => void finishAndMaybeNavigate("/register?tier=global")} variant="secondary">
              {t("upgrade.getGlobal")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

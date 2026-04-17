"use client";

import { FileText, Heart, Home, Phone, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useCrmStatus } from "@/hooks/useCrmStatus";
import { CRM_STATUS_ORDER, getCrmStatusLabel } from "@/lib/listing-search";
import { cn } from "@/lib/utils";

const iconMap = {
  favorite: Heart,
  contacted: Phone,
  visited: Home,
  offer: FileText,
  discard: X,
} as const;

export function CrmActions({
  listingId,
}: {
  listingId: string;
}) {
  const t = useTranslations("listingDetail");
  const { crmEntry, updating, updateStatus } = useCrmStatus(listingId);

  return (
    <section className="space-y-3" data-testid="crm-actions">
      <div>
        <h2 className="text-xl font-semibold text-slate-950">{t("crmActions")}</h2>
        <p className="text-sm text-slate-500">{t("crmSubtitle")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {CRM_STATUS_ORDER.map((status) => {
          const Icon = iconMap[status];
          const active = crmEntry?.status === status;

          return (
            <Button
              className={cn(active ? "" : "bg-white text-slate-700 hover:bg-slate-50")}
              data-testid={`crm-action-${status}`}
              disabled={updating}
              key={status}
              onClick={() => void updateStatus(active ? null : status)}
              variant={active ? "default" : "outline"}
            >
              <Icon className="mr-2 h-4 w-4" />
              {getCrmStatusLabel(t, status)}
            </Button>
          );
        })}
      </div>
    </section>
  );
}

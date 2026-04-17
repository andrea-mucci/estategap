"use client";

import { useLocale } from "next-intl";
import { useSession } from "next-auth/react";
import { useState } from "react";

import { PortfolioPropertyTable } from "@/components/portfolio/PortfolioPropertyTable";
import { PortfolioSummaryCards } from "@/components/portfolio/PortfolioSummaryCards";
import { PropertyFormDialog } from "@/components/portfolio/PropertyFormDialog";
import { Button } from "@/components/ui/button";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { useExchangeRates } from "@/hooks/useExchangeRates";
import { usePortfolio, type PortfolioPropertyInput } from "@/hooks/usePortfolio";
import type { PortfolioProperty } from "@/lib/api";
import { useNotificationStore } from "@/stores/notificationStore";

export function PortfolioClient() {
  const locale = useLocale();
  const { data: session } = useSession();
  const preferredCurrency = session?.user.preferredCurrency ?? "EUR";
  const pushToast = useNotificationStore((state) => state.pushToast);
  const { rates } = useExchangeRates();
  const portfolio = usePortfolio();
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [editingProperty, setEditingProperty] = useState<PortfolioProperty | null>(null);

  async function handleSubmit(values: PortfolioPropertyInput) {
    try {
      if (editingProperty) {
        await portfolio.updateProperty(editingProperty.id, values);
      } else {
        await portfolio.createProperty(values);
      }
      setDialogOpen(false);
      setEditingProperty(null);
    } catch (error) {
      pushToast({
        type: "error",
        title: "Portfolio update failed",
        description: error instanceof Error ? error.message : "Unable to save property.",
        durationMs: 4000,
      });
    }
  }

  async function handleDelete(property: PortfolioProperty) {
    const confirmed = window.confirm(
      `Delete ${property.address} from your portfolio? This cannot be undone.`,
    );

    if (!confirmed) {
      return;
    }

    try {
      await portfolio.deleteProperty(property.id);
    } catch (error) {
      pushToast({
        type: "error",
        title: "Delete failed",
        description: error instanceof Error ? error.message : "Unable to remove property.",
        durationMs: 4000,
      });
    }
  }

  if (portfolio.error) {
    return (
      <ErrorDisplay
        error={
          portfolio.error instanceof Error
            ? portfolio.error
            : new Error("Portfolio data is unavailable.")
        }
        refetch={() => {
          void window.location.reload();
        }}
      />
    );
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
            Portfolio tracker
          </p>
          <h1 className="text-3xl font-semibold text-slate-950">Your portfolio</h1>
          <p className="max-w-2xl text-sm text-slate-500">
            Figures are displayed in {preferredCurrency} for the current session ({locale.toUpperCase()}).
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingProperty(null);
            setDialogOpen(true);
          }}
        >
          Add property
        </Button>
      </div>

      <PortfolioSummaryCards
        isLoading={portfolio.isLoading}
        preferredCurrency={preferredCurrency}
        rates={rates}
        summary={portfolio.summary}
      />

      <PortfolioPropertyTable
        deletingId={portfolio.deletingId}
        isLoading={portfolio.isLoading}
        onAdd={() => {
          setEditingProperty(null);
          setDialogOpen(true);
        }}
        onDelete={handleDelete}
        onEdit={(property) => {
          setEditingProperty(property);
          setDialogOpen(true);
        }}
        preferredCurrency={preferredCurrency}
        properties={portfolio.properties}
        rates={rates}
      />

      <div className="fixed bottom-6 right-6 z-20">
        <Button
          className="shadow-xl"
          onClick={() => {
            setEditingProperty(null);
            setDialogOpen(true);
          }}
          size="lg"
        >
          Add property
        </Button>
      </div>

      <PropertyFormDialog
        initialValues={editingProperty}
        isPending={portfolio.isSaving}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setEditingProperty(null);
          }
        }}
        onSubmit={handleSubmit}
        open={isDialogOpen}
      />
    </section>
  );
}

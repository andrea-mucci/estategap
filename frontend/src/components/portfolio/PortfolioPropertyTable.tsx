"use client";

import { useLocale } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PortfolioProperty } from "@/lib/api";
import { convertFromEUR, formatCurrency } from "@/lib/currency";

function calculateYield(property: PortfolioProperty) {
  if (property.purchase_price_eur <= 0) {
    return 0;
  }
  return ((property.monthly_rental_income_eur * 12) / property.purchase_price_eur) * 100;
}

export function PortfolioPropertyTable({
  properties,
  isLoading,
  deletingId,
  preferredCurrency,
  rates,
  onAdd,
  onEdit,
  onDelete,
}: {
  properties: PortfolioProperty[];
  isLoading: boolean;
  deletingId: string | null;
  preferredCurrency: string;
  rates: Record<string, number>;
  onAdd: () => void;
  onEdit: (property: PortfolioProperty) => void;
  onDelete: (property: PortfolioProperty) => void;
}) {
  const locale = useLocale();

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>Portfolio properties</CardTitle>
          <p className="text-sm text-slate-500">
            Track acquisition cost, rental income, and estimate coverage in one place.
          </p>
        </div>
        <Button onClick={onAdd}>Add property</Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton className="h-14 w-full" key={index} />
            ))}
          </div>
        ) : properties.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
            <p className="text-lg font-semibold text-slate-950">No properties yet</p>
            <p className="mt-2 text-sm text-slate-500">
              Add your first property to unlock gain / loss and yield tracking.
            </p>
            <Button className="mt-4" onClick={onAdd}>
              Add property
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-[24px] border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Address</th>
                  <th className="px-4 py-3 font-medium">Country</th>
                  <th className="px-4 py-3 font-medium">Purchase price</th>
                  <th className="px-4 py-3 font-medium">Purchase date</th>
                  <th className="px-4 py-3 font-medium">Monthly rental</th>
                  <th className="px-4 py-3 font-medium">Estimated value</th>
                  <th className="px-4 py-3 font-medium">Gain / loss</th>
                  <th className="px-4 py-3 font-medium">Yield</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {properties.map((property) => {
                  const estimatedValue = property.estimated_value_eur
                    ? convertFromEUR(property.estimated_value_eur, preferredCurrency, rates)
                    : null;
                  const gainLossEUR =
                    property.estimated_value_eur == null
                      ? null
                      : property.estimated_value_eur - property.purchase_price_eur;
                  const gainLoss = gainLossEUR == null
                    ? null
                    : convertFromEUR(gainLossEUR, preferredCurrency, rates);
                  const yieldPct = calculateYield(property);

                  return (
                    <tr className="border-t border-slate-200" key={property.id}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-950">{property.address}</div>
                        <div className="text-xs text-slate-500">{property.property_type}</div>
                      </td>
                      <td className="px-4 py-3">{property.country}</td>
                      <td className="px-4 py-3">
                        {formatCurrency(
                          convertFromEUR(property.purchase_price_eur, preferredCurrency, rates),
                          preferredCurrency,
                          locale,
                        )}
                      </td>
                      <td className="px-4 py-3">{property.purchase_date}</td>
                      <td className="px-4 py-3">
                        {formatCurrency(
                          convertFromEUR(property.monthly_rental_income_eur, preferredCurrency, rates),
                          preferredCurrency,
                          locale,
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {estimatedValue == null
                          ? "Not available"
                          : formatCurrency(estimatedValue, preferredCurrency, locale)}
                      </td>
                      <td
                        className={
                          gainLoss == null
                            ? "px-4 py-3 text-slate-400"
                            : gainLoss >= 0
                              ? "px-4 py-3 font-medium text-emerald-700"
                              : "px-4 py-3 font-medium text-rose-700"
                        }
                      >
                        {gainLoss == null
                          ? "Not available"
                          : formatCurrency(gainLoss, preferredCurrency, locale)}
                      </td>
                      <td className="px-4 py-3">{yieldPct.toFixed(1)}%</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <Button onClick={() => onEdit(property)} size="sm" variant="outline">
                            Edit
                          </Button>
                          <Button
                            disabled={deletingId === property.id}
                            onClick={() => onDelete(property)}
                            size="sm"
                            variant="destructive"
                          >
                            {deletingId === property.id ? "Deleting..." : "Delete"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

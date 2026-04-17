"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCountries } from "@/hooks/useCountries";
import { type PortfolioProperty } from "@/lib/api";
import { SUPPORTED_CURRENCIES } from "@/lib/currency";
import type { PortfolioPropertyInput } from "@/hooks/usePortfolio";

const propertySchema = z.object({
  address: z.string().trim().min(3, "Address is required."),
  country: z.string().trim().length(2, "Country is required."),
  purchase_price: z.coerce.number().positive("Purchase price must be greater than 0."),
  purchase_currency: z.string().trim().length(3, "Currency is required."),
  purchase_date: z
    .string()
    .trim()
    .min(1, "Purchase date is required.")
    .refine((value) => !Number.isNaN(Date.parse(value)), "Purchase date is invalid."),
  monthly_rental_income: z.coerce
    .number()
    .min(0, "Monthly rental income must be 0 or greater."),
  area_m2: z.preprocess(
    (value) => (value === "" || value === null || value === undefined ? undefined : Number(value)),
    z.number().positive("Area must be greater than 0.").optional(),
  ),
  property_type: z.enum(["residential", "commercial", "industrial", "land"]),
  notes: z.string().trim().optional(),
});

type PropertyFormValues = z.infer<typeof propertySchema>;

function toDefaults(initialValues?: PortfolioProperty | null): PropertyFormValues {
  return {
    address: initialValues?.address ?? "",
    country: initialValues?.country ?? "ES",
    purchase_price: initialValues?.purchase_price ?? 0,
    purchase_currency: initialValues?.purchase_currency ?? "EUR",
    purchase_date: initialValues?.purchase_date ?? new Date().toISOString().slice(0, 10),
    monthly_rental_income: initialValues?.monthly_rental_income ?? 0,
    area_m2: initialValues?.area_m2 ?? undefined,
    property_type: initialValues?.property_type ?? "residential",
    notes: initialValues?.notes ?? "",
  };
}

function errorMessage(error?: string) {
  return error ? <p className="mt-1 text-xs text-rose-600">{error}</p> : null;
}

export function PropertyFormDialog({
  open,
  onOpenChange,
  initialValues,
  isPending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialValues?: PortfolioProperty | null;
  isPending?: boolean;
  onSubmit: (values: PortfolioPropertyInput) => Promise<void>;
}) {
  const countries = useCountries();
  const form = useForm<PropertyFormValues>({
    resolver: zodResolver(propertySchema),
    defaultValues: toDefaults(initialValues),
  });

  useEffect(() => {
    form.reset(toDefaults(initialValues));
  }, [form, initialValues, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold text-slate-950">
            {initialValues ? "Edit property" : "Add property"}
          </h2>
          <p className="text-sm text-slate-500">
            Capture the purchase details you want tracked in the portfolio dashboard.
          </p>
        </div>

        <form
          className="mt-6 space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            await onSubmit({
              ...values,
              country: values.country.toUpperCase(),
              purchase_currency: values.purchase_currency.toUpperCase(),
              notes: values.notes?.trim() || undefined,
            });
          })}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="address">
                Address
              </label>
              <Input id="address" {...form.register("address")} />
              {errorMessage(form.formState.errors.address?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="country">
                Country
              </label>
              <Select id="country" {...form.register("country")}>
                {(countries.data?.items ?? []).map((country) => (
                  <option key={country.code} value={country.code}>
                    {country.name}
                  </option>
                ))}
              </Select>
              {errorMessage(form.formState.errors.country?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="purchase_currency">
                Purchase currency
              </label>
              <Select id="purchase_currency" {...form.register("purchase_currency")}>
                {SUPPORTED_CURRENCIES.map((currency) => (
                  <option key={currency} value={currency}>
                    {currency}
                  </option>
                ))}
              </Select>
              {errorMessage(form.formState.errors.purchase_currency?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="purchase_price">
                Purchase price
              </label>
              <Input id="purchase_price" min="0" step="0.01" type="number" {...form.register("purchase_price")} />
              {errorMessage(form.formState.errors.purchase_price?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="purchase_date">
                Purchase date
              </label>
              <Input
                id="purchase_date"
                max={new Date().toISOString().slice(0, 10)}
                type="date"
                {...form.register("purchase_date")}
              />
              {errorMessage(form.formState.errors.purchase_date?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="monthly_rental_income">
                Monthly rental income
              </label>
              <Input
                id="monthly_rental_income"
                min="0"
                step="0.01"
                type="number"
                {...form.register("monthly_rental_income")}
              />
              {errorMessage(form.formState.errors.monthly_rental_income?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="area_m2">
                Area (m²)
              </label>
              <Input id="area_m2" min="0" step="0.01" type="number" {...form.register("area_m2")} />
              {errorMessage(form.formState.errors.area_m2?.message)}
            </div>

            <div>
              <label className="text-sm font-medium text-slate-700" htmlFor="property_type">
                Property type
              </label>
              <Select id="property_type" {...form.register("property_type")}>
                <option value="residential">Residential</option>
                <option value="commercial">Commercial</option>
                <option value="industrial">Industrial</option>
                <option value="land">Land</option>
              </Select>
              {errorMessage(form.formState.errors.property_type?.message)}
            </div>

            <div className="md:col-span-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="notes">
                Notes
              </label>
              <Textarea id="notes" {...form.register("notes")} />
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={isPending} type="submit">
              {isPending ? "Saving..." : "Save property"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

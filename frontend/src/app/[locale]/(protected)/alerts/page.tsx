"use client";

import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useCountries } from "@/hooks/useCountries";
import { useRouter } from "@/i18n/routing";
import { PROPERTY_TYPE_OPTIONS, type PropertyCategory } from "@/lib/listing-search";
import { useNotificationStore } from "@/stores/notificationStore";
import { useOnboardingStore } from "@/stores/onboardingStore";

type AlertFormValues = {
  country: string;
  maxPrice: string;
  minArea: string;
  propertyCategory: PropertyCategory;
  propertyType: string;
};

const categoryByType = Object.entries(PROPERTY_TYPE_OPTIONS).reduce<Record<string, PropertyCategory>>(
  (accumulator, [category, values]) => {
    values.forEach((value) => {
      accumulator[value] = category as PropertyCategory;
    });
    return accumulator;
  },
  {},
);

function getDefaultValues(searchParams: Pick<URLSearchParams, "get">): AlertFormValues {
  const propertyType = searchParams.get("propertyType") ?? "";
  const propertyCategory = categoryByType[propertyType] ?? "residential";

  return {
    country: searchParams.get("country") ?? "ES",
    maxPrice: searchParams.get("maxPrice") ?? "",
    minArea: searchParams.get("minArea") ?? "",
    propertyCategory,
    propertyType,
  };
}

export default function AlertsPage() {
  const router = useRouter();
  const tNav = useTranslations("nav");
  const tCommon = useTranslations("common");
  const tSearch = useTranslations("searchPage");
  const tOnboarding = useTranslations("onboarding");
  const searchParams = useSearchParams();
  const { data } = useCountries();
  const pushToast = useNotificationStore((state) => state.pushToast);
  const active = useOnboardingStore((state) => state.active);
  const currentStep = useOnboardingStore((state) => state.currentStep);
  const advanceStep = useOnboardingStore((state) => state.advanceStep);

  const defaultValues = useMemo(() => getDefaultValues(searchParams), [searchParams]);
  const hasPrefill = searchParams.toString().length > 0;
  const form = useForm<AlertFormValues>({
    defaultValues,
  });
  const propertyTypes = PROPERTY_TYPE_OPTIONS[form.watch("propertyCategory")] ?? [];

  useEffect(() => {
    form.reset(defaultValues);
  }, [defaultValues, form]);

  useEffect(() => {
    if (!hasPrefill) {
      return;
    }

    document.getElementById("alert-form")?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [hasPrefill]);

  function continueToDashboard() {
    advanceStep();
    router.push("/dashboard");
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-slate-950">{tNav("alerts")}</h1>
        <p className="max-w-2xl text-sm leading-7 text-slate-500">
          Capture the criteria you want EstateGap to monitor, then promote it into your ongoing workflow.
        </p>
      </div>

      <Card className="max-w-4xl">
        <CardHeader>
          <CardTitle>Alert setup</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            id="alert-form"
            onSubmit={form.handleSubmit(() => {
              pushToast({
                type: "success",
                title: "Alert draft saved",
                description: "Your criteria are ready to monitor as soon as you activate the workflow.",
                durationMs: 3200,
              });

              if (active && currentStep === "ALERT") {
                continueToDashboard();
              }
            })}
          >
            <div className="grid gap-5 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="country">{tSearch("country")}</Label>
                <Select id="country" {...form.register("country")}>
                  {(data?.items ?? []).map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="propertyCategory">{tSearch("category")}</Label>
                <Select
                  id="propertyCategory"
                  {...form.register("propertyCategory")}
                  onChange={(event) => {
                    form.setValue("propertyCategory", event.target.value as PropertyCategory);
                    form.setValue("propertyType", "");
                  }}
                >
                  <option value="residential">Residential</option>
                  <option value="commercial">Commercial</option>
                  <option value="industrial">Industrial</option>
                  <option value="land">Land</option>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="propertyType">{tSearch("type")}</Label>
                <Select id="propertyType" {...form.register("propertyType")}>
                  <option value="">{tSearch("allPropertyTypes")}</option>
                  {propertyTypes.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="maxPrice">{tSearch("priceRange")}</Label>
                <Input id="maxPrice" placeholder="450000" {...form.register("maxPrice")} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="minArea">{tSearch("areaRange")}</Label>
                <Input id="minArea" placeholder="80" {...form.register("minArea")} />
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button type="submit">{active && currentStep === "ALERT" ? tOnboarding("saveAlert") : tCommon("save")}</Button>
              {active && currentStep === "ALERT" ? (
                <Button onClick={continueToDashboard} type="button" variant="ghost">
                  {tOnboarding("skipSetup")}
                </Button>
              ) : (
                <Button onClick={() => form.reset(defaultValues)} type="button" variant="ghost">
                  {tCommon("cancel")}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}

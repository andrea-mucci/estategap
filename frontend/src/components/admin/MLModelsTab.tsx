"use client";

import { formatDistanceToNow } from "date-fns";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminMLModels, useRetrainMutation } from "@/hooks/useAdminML";

export function MLModelsTab() {
  const modelsQuery = useAdminMLModels();
  const retrainMutation = useRetrainMutation();

  if (modelsQuery.error) {
    return (
      <ErrorDisplay
        error={modelsQuery.error instanceof Error ? modelsQuery.error : new Error("Unable to load ML models.")}
        refetch={() => {
          void modelsQuery.refetch();
        }}
      />
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>ML model registry</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {modelsQuery.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton className="h-14 w-full" key={index} />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-[24px] border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Country</th>
                  <th className="px-4 py-3 font-medium">Version</th>
                  <th className="px-4 py-3 font-medium">MAPE</th>
                  <th className="px-4 py-3 font-medium">MAE</th>
                  <th className="px-4 py-3 font-medium">R²</th>
                  <th className="px-4 py-3 font-medium">Trained</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {modelsQuery.models.map((model) => (
                  <tr className="border-t border-slate-200" key={model.id}>
                    <td className="px-4 py-3 font-medium text-slate-950">{model.country}</td>
                    <td className="px-4 py-3">{model.version}</td>
                    <td className="px-4 py-3">{model.mape.toFixed(2)}%</td>
                    <td className="px-4 py-3">{model.mae.toFixed(2)}</td>
                    <td className="px-4 py-3">{model.r2.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      {formatDistanceToNow(new Date(model.trained_at), { addSuffix: true })}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                          model.train_status === "training"
                            ? "bg-amber-50 text-amber-700"
                            : model.is_active
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {model.train_status === "idle" ? (model.is_active ? "active" : "idle") : model.train_status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        disabled={
                          model.train_status === "training" ||
                          (retrainMutation.isPending && retrainMutation.variables === model.country)
                        }
                        onClick={() => retrainMutation.mutate(model.country)}
                        size="sm"
                      >
                        {model.train_status === "training"
                          ? "Training..."
                          : retrainMutation.isPending && retrainMutation.variables === model.country
                            ? "Queueing..."
                            : "Retrain now"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminSystem } from "@/hooks/useAdminSystem";

function formatBytes(bytes: number) {
  if (bytes <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** power;
  return `${value.toFixed(power === 0 ? 0 : 1)} ${units[power]}`;
}

export function SystemHealthTab() {
  const system = useAdminSystem();

  if (system.error) {
    return (
      <ErrorDisplay
        error={system.error instanceof Error ? system.error : new Error("Unable to load system health.")}
        refetch={() => {
          void system.refetch();
        }}
      />
    );
  }

  if (system.isLoading || !system.health) {
    return (
      <div className="grid gap-4 xl:grid-cols-2">
        {Array.from({ length: 2 }).map((_, index) => (
          <Skeleton className="h-52 w-full" key={index} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Database</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-slate-600">
          <p>Size: {formatBytes(system.health.database.size_bytes)}</p>
          <p>Active connections: {system.health.database.active_connections.toLocaleString()}</p>
          <p>Waiting connections: {system.health.database.waiting_connections.toLocaleString()}</p>
          <p>Max connections: {system.health.database.max_connections.toLocaleString()}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Redis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-slate-600">
          <p>Used memory: {formatBytes(system.health.redis.used_memory_bytes)}</p>
          <p>Max memory: {formatBytes(system.health.redis.max_memory_bytes)}</p>
          <p>Hit rate: {(system.health.redis.hit_rate * 100).toFixed(1)}%</p>
          <p>Connected clients: {system.health.redis.connected_clients.toLocaleString()}</p>
        </CardContent>
      </Card>
    </div>
  );
}

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
      <div className="grid gap-4 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton className="h-52 w-full" key={index} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>NATS</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {system.health.nats.subjects.length === 0 ? (
            <p className="text-sm text-slate-500">No JetStream subjects were reported.</p>
          ) : (
            system.health.nats.subjects.map((subject) => (
              <div className="rounded-[20px] border border-slate-200 p-4" key={subject.subject}>
                <p className="font-medium text-slate-950">{subject.subject}</p>
                <p className="mt-2 text-sm text-slate-500">
                  Lag: {subject.consumer_lag.toLocaleString()} · Messages: {subject.message_count.toLocaleString()}
                </p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

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

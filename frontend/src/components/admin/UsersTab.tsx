"use client";

import { formatDistanceToNow } from "date-fns";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorDisplay } from "@/components/ui/ErrorDisplay";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminUsers } from "@/hooks/useAdminUsers";

export function UsersTab() {
  const users = useAdminUsers();
  const totalPages = Math.max(1, Math.ceil(users.total / users.limit));

  if (users.error) {
    return (
      <ErrorDisplay
        error={users.error instanceof Error ? users.error : new Error("Unable to load users.")}
        refetch={() => {
          void users.refetch();
        }}
      />
    );
  }

  return (
    <Card>
      <CardHeader className="space-y-4">
        <div>
          <CardTitle>Users</CardTitle>
        </div>
        <div className="grid gap-3 md:grid-cols-[2fr,1fr]">
          <Input
            onChange={(event) => users.setQuery(event.target.value)}
            placeholder="Search by email or name"
            value={users.query}
          />
          <Select onChange={(event) => users.setTier(event.target.value)} value={users.tier}>
            <option value="">All tiers</option>
            <option value="free">Free</option>
            <option value="basic">Basic</option>
            <option value="pro">Pro</option>
            <option value="global">Global</option>
            <option value="api">API</option>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {users.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton className="h-14 w-full" key={index} />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-[24px] border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Tier</th>
                  <th className="px-4 py-3 font-medium">Last active</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {users.users.map((user) => (
                  <tr className="border-t border-slate-200" key={user.id}>
                    <td className="px-4 py-3 font-medium text-slate-950">{user.email}</td>
                    <td className="px-4 py-3">{user.name ?? "—"}</td>
                    <td className="px-4 py-3">{user.role}</td>
                    <td className="px-4 py-3">{user.subscription_tier}</td>
                    <td className="px-4 py-3">
                      {user.last_active_at
                        ? formatDistanceToNow(new Date(user.last_active_at), { addSuffix: true })
                        : "No activity"}
                    </td>
                    <td className="px-4 py-3">
                      {formatDistanceToNow(new Date(user.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">
            Page {users.page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={users.page <= 1}
              onClick={() => users.setPage(users.page - 1)}
              type="button"
            >
              Previous
            </button>
            <button
              className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={users.page >= totalPages}
              onClick={() => users.setPage(users.page + 1)}
              type="button"
            >
              Next
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

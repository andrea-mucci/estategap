import type { PropsWithChildren } from "react";

import { Header } from "@/components/layout/Header";
import { NotificationToasts } from "@/components/layout/NotificationToasts";
import { Sidebar } from "@/components/layout/Sidebar";

export function MainLayout({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[18rem_1fr]">
      <Sidebar />
      <div className="min-w-0">
        <Header />
        <main className="px-4 py-6 sm:px-6">{children}</main>
      </div>
      <NotificationToasts />
    </div>
  );
}

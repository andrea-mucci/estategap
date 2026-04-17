"use client";

import type { PropsWithChildren } from "react";
import { createContext, useContext, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";

import { WebSocketManager } from "@/lib/ws";

const WebSocketContext = createContext<WebSocketManager | null>(null);

export function WSProvider({ children }: PropsWithChildren) {
  const { data: session, status } = useSession();
  const managerRef = useRef<WebSocketManager | null>(null);

  if (!managerRef.current) {
    managerRef.current = new WebSocketManager();
  }

  useEffect(() => {
    const manager = managerRef.current;

    if (!manager) {
      return;
    }

    if (status === "authenticated" && session?.accessToken) {
      manager.connect(session.accessToken);
      return () => manager.disconnect();
    }

    manager.disconnect();
  }, [session?.accessToken, status]);

  return (
    <WebSocketContext.Provider value={managerRef.current}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const manager = useContext(WebSocketContext);

  if (!manager) {
    throw new Error("useWebSocket must be used inside a WSProvider");
  }

  return manager;
}

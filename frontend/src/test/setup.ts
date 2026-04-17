import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

import { server } from "./msw";

vi.mock("next-auth/react", () => ({
  SessionProvider: ({ children }: PropsWithChildren) => children,
  useSession: () => ({
    data: {
      accessToken: "test-access-token",
      user: {
        email: "analyst@estategap.com",
      },
    },
    status: "authenticated",
    update: vi.fn(),
  }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: () => (key: string) => key,
}));

vi.mock("next/image", () => ({
  default: (props: Record<string, unknown>) => createElement("img", props),
}));

vi.mock("@/i18n/routing", () => ({
  Link: ({ children, href }: PropsWithChildren<{ href: string }>) =>
    createElement("a", { href }, children),
}));

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
  cleanup();
});

afterAll(() => {
  server.close();
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

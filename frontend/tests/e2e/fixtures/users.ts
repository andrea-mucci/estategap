export type Tier = "free" | "basic" | "pro" | "global" | "api" | "admin";

export const TIER_USERS: Record<Tier, { email: string; password: string }> = {
  free: { email: "free@test.estategap.com", password: "secret" },
  basic: { email: "basic@test.estategap.com", password: "secret" },
  pro: { email: "pro@test.estategap.com", password: "secret" },
  global: { email: "global@test.estategap.com", password: "secret" },
  api: { email: "api@test.estategap.com", password: "secret" },
  admin: { email: "admin@estategap.com", password: "secret12345" },
};

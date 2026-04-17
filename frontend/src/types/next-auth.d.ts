import "next-auth";
import "next-auth/jwt";

type SubscriptionTier = "free" | "basic" | "pro" | "global" | "api";
type UserRole = "user" | "admin";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      email: string;
      name: string | null;
      image: string | null;
      subscriptionTier: SubscriptionTier;
      preferredCurrency: string;
      role: UserRole;
    };
    accessToken: string;
    accessTokenExpires: number;
    refreshToken: string;
    error?: string;
  }

  interface User {
    id: string;
    email: string;
    name: string | null;
    image: string | null;
    subscriptionTier: SubscriptionTier;
    preferredCurrency: string;
    role: UserRole;
    accessToken: string;
    accessTokenExpires: number;
    refreshToken: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    sub?: string;
    accessToken: string;
    accessTokenExpires: number;
    refreshToken: string;
    subscriptionTier: SubscriptionTier;
    preferredCurrency: string;
    role: UserRole;
    error?: string;
  }
}

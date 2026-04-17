import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

import type { components } from "@/types/api";

type TokenPair = components["schemas"]["TokenPair"];
type UserProfile = components["schemas"]["UserProfile"];

function getApiUrl(path: string) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
  return new URL(path, baseUrl).toString();
}

function toRole(profile?: UserProfile): "user" | "admin" {
  if (profile?.role === "admin" || profile?.role === "user") {
    return profile.role;
  }

  if (profile?.email?.endsWith("@estategap.com")) {
    return "admin";
  }

  return "user";
}

function mapAuthPayload(payload: TokenPair) {
  const profile = payload.user;

  return {
    id: profile?.id ?? "oauth-user",
    email: profile?.email ?? "",
    name: profile?.display_name ?? profile?.email ?? null,
    image: profile?.avatar_url ?? null,
    subscriptionTier: profile?.subscription_tier ?? "free",
    preferredCurrency: profile?.preferred_currency ?? "EUR",
    role: toRole(profile),
    accessToken: payload.access_token,
    accessTokenExpires: Date.now() + payload.expires_in * 1000,
    refreshToken: payload.refresh_token,
  } as const;
}

async function refreshAccessToken(token: {
  refreshToken: string;
}) {
  try {
    const response = await fetch(getApiUrl("/api/v1/auth/refresh"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: token.refreshToken,
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to refresh access token");
    }

    const payload = (await response.json()) as TokenPair;
    const mapped = mapAuthPayload(payload);

    return {
      ...token,
      accessToken: mapped.accessToken,
      accessTokenExpires: mapped.accessTokenExpires,
      refreshToken: mapped.refreshToken,
      subscriptionTier: mapped.subscriptionTier,
      preferredCurrency: mapped.preferredCurrency,
      role: mapped.role,
      error: undefined,
    };
  } catch {
    return {
      ...token,
      error: "RefreshTokenExpired",
    };
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  secret: process.env.NEXTAUTH_SECRET,
  session: {
    strategy: "jwt",
  },
  providers: [
    Credentials({
      name: "Email and Password",
      credentials: {
        email: {
          label: "Email",
          type: "email",
        },
        password: {
          label: "Password",
          type: "password",
        },
      },
      async authorize(credentials) {
        const email = `${credentials?.email ?? ""}`.trim();
        const password = `${credentials?.password ?? ""}`;

        if (!email || password.length < 8) {
          return null;
        }

        const response = await fetch(getApiUrl("/api/v1/auth/login"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
          return null;
        }

        const payload = (await response.json()) as TokenPair;
        return mapAuthPayload(payload);
      },
    }),
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
  ],
  callbacks: {
    async jwt({ token, user, account, trigger, session }) {
      if (trigger === "update" && session?.preferredCurrency) {
        token.preferredCurrency = session.preferredCurrency;
      }

      if (user) {
        token.sub = user.id;
        token.email = user.email;
        token.name = user.name;
        token.picture = user.image;
        token.accessToken = user.accessToken;
        token.accessTokenExpires = user.accessTokenExpires;
        token.refreshToken = user.refreshToken;
        token.subscriptionTier = user.subscriptionTier;
        token.preferredCurrency = user.preferredCurrency;
        token.role = user.role;
      }

      if (account?.provider === "google" && account.access_token) {
        token.accessToken = account.access_token;
        token.accessTokenExpires = account.expires_at
          ? account.expires_at * 1000
          : Date.now() + 60 * 60 * 1000;
        token.refreshToken = account.refresh_token ?? token.refreshToken ?? "";
        token.subscriptionTier = token.subscriptionTier ?? "free";
        token.preferredCurrency = token.preferredCurrency ?? "EUR";
        token.role = token.role ?? "user";
      }

      if (
        token.accessToken &&
        token.accessTokenExpires &&
        Date.now() < token.accessTokenExpires - 60_000
      ) {
        return token;
      }

      if (!token.refreshToken) {
        return token;
      }

      return refreshAccessToken({
        refreshToken: token.refreshToken,
      });
    },
    async session({ session, token }) {
      if (!session.user) {
        return session;
      }

      session.user.id = token.sub ?? "";
      session.user.email = token.email ?? "";
      session.user.name = token.name ?? null;
      session.user.image = typeof token.picture === "string" ? token.picture : null;
      session.user.subscriptionTier = token.subscriptionTier ?? "free";
      session.user.preferredCurrency = token.preferredCurrency ?? "EUR";
      session.user.role = token.role ?? "user";
      session.accessToken = token.accessToken;
      session.accessTokenExpires = token.accessTokenExpires;
      session.refreshToken = token.refreshToken;
      session.error = token.error;

      return session;
    },
  },
  events: {
    async signOut({ token }) {
      if (!token?.refreshToken || !token.accessToken) {
        return;
      }

      await fetch(getApiUrl("/api/v1/auth/logout"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token.accessToken}`,
        },
        body: JSON.stringify({
          refresh_token: token.refreshToken,
        }),
      }).catch(() => undefined);
    },
  },
});

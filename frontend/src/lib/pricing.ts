export type PricingTierId = "free" | "basic" | "pro" | "global" | "api";

export type PricingTier = {
  id: PricingTierId;
  price: number | null;
  highlighted: boolean;
  ctaHref: string;
};

export const PRICING_TIERS: PricingTier[] = [
  {
    id: "free",
    price: 0,
    highlighted: false,
    ctaHref: "/register?tier=free",
  },
  {
    id: "basic",
    price: 19,
    highlighted: false,
    ctaHref: "/register?tier=basic",
  },
  {
    id: "pro",
    price: 49,
    highlighted: true,
    ctaHref: "/register?tier=pro",
  },
  {
    id: "global",
    price: 99,
    highlighted: false,
    ctaHref: "/register?tier=global",
  },
  {
    id: "api",
    price: null,
    highlighted: false,
    ctaHref: "/contact?subject=api",
  },
];

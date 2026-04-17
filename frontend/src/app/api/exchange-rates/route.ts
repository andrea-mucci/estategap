import { NextResponse } from "next/server";

const ECB_RATES_URL =
  "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml";

type CachedRates = {
  rates: Record<string, number>;
  updatedAt: number;
};

declare global {
  var __estategapExchangeRatesCache: CachedRates | undefined;
}

function getCachedRates() {
  const cache = globalThis.__estategapExchangeRatesCache;
  if (!cache) {
    return null;
  }

  if (Date.now() - cache.updatedAt > 24 * 60 * 60 * 1000) {
    return null;
  }

  return cache.rates;
}

function setCachedRates(rates: Record<string, number>) {
  globalThis.__estategapExchangeRatesCache = {
    rates,
    updatedAt: Date.now(),
  };
}

function parseRates(xml: string) {
  const rates: Record<string, number> = {
    EUR: 1,
  };

  for (const match of xml.matchAll(/currency=['"]([A-Z]{3})['"]\s+rate=['"]([0-9.]+)['"]/g)) {
    const [, currency, rawRate] = match;
    const rate = Number(rawRate);

    if (Number.isFinite(rate) && rate > 0) {
      rates[currency] = rate;
    }
  }

  return rates;
}

export async function GET() {
  const cachedRates = getCachedRates();
  if (cachedRates) {
    return NextResponse.json({ rates: cachedRates, source: "cache" });
  }

  try {
    const response = await fetch(ECB_RATES_URL, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`ECB returned ${response.status}`);
    }

    const xml = await response.text();
    const rates = parseRates(xml);
    setCachedRates(rates);

    return NextResponse.json({ rates, source: "ecb" });
  } catch (error) {
    const fallbackRates = globalThis.__estategapExchangeRatesCache?.rates;
    if (fallbackRates) {
      return NextResponse.json({ rates: fallbackRates, source: "stale-cache" });
    }

    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Failed to fetch exchange rates",
      },
      { status: 503 },
    );
  }
}

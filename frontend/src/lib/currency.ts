export const SUPPORTED_CURRENCIES = [
  "EUR",
  "USD",
  "GBP",
  "CHF",
  "SEK",
  "NOK",
  "DKK",
  "PLN",
] as const;

export function convertFromEUR(
  amountEUR: number,
  currency: string,
  rates: Record<string, number>,
) {
  const normalizedCurrency = currency.toUpperCase();
  if (normalizedCurrency === "EUR") {
    return amountEUR;
  }

  const rate = rates[normalizedCurrency];
  if (!Number.isFinite(rate) || rate <= 0) {
    return amountEUR;
  }

  return amountEUR * rate;
}

export function formatCurrency(amount: number, currency: string, locale: string) {
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency.toUpperCase()} ${amount.toLocaleString(locale)}`;
  }
}

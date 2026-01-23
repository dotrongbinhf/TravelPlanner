import { CURRENCIES } from "@/constants/currency";

export const getLocaleFromCurrencyCode = (currencyCode: string): string => {
  return CURRENCIES.find((currency) => currency.code === currencyCode)?.locale ?? "vi-VN";
} 
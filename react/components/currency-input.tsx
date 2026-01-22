"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import { CURRENCIES } from "@/constants/currency";

interface CurrencyInputProps {
  value: string;
  currency: string;
  onValueChange: (value: string) => void;
  onCurrencyChange: (currency: string) => void;
}

export function CurrencyInput({
  value,
  currency,
  onValueChange,
  onCurrencyChange,
}: CurrencyInputProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedCurrency =
    CURRENCIES.find((c) => c.code === currency) || CURRENCIES[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Remove non-numeric characters
    const inputValue = e.target.value.replace(/[^0-9]/g, "");
    onValueChange(inputValue);
  };

  const formatDisplayValue = (val: string) => {
    if (!val) return "";
    const num = parseInt(val, 10);
    if (isNaN(num)) return val;
    return num.toLocaleString(selectedCurrency.locale);
  };

  return (
    <div
      ref={containerRef}
      className={`flex border rounded-md transition-all duration-200 ${
        isFocused
          ? "border-blue-500 ring-2 ring-blue-500"
          : "border-gray-300 hover:border-gray-400"
      }`}
    >
      <input
        type="text"
        value={formatDisplayValue(value)}
        onChange={handleValueChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        placeholder="0"
        className="flex-1 px-3 py-2 rounded-l-md focus:outline-none bg-transparent"
      />
      <div className="relative">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="h-full px-3 py-2 bg-gray-50 border-l border-gray-300 rounded-r-md flex items-center gap-1 hover:bg-gray-100 transition-colors cursor-pointer"
        >
          <span className="text-sm font-medium text-gray-700">
            {selectedCurrency.code}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${
              isOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        {isOpen && (
          <div className="absolute right-0 mt-1 w-30 bg-white border border-gray-200 rounded-md shadow-lg z-50">
            {CURRENCIES.map((curr) => (
              <button
                key={curr.code}
                type="button"
                onClick={() => {
                  onCurrencyChange(curr.code);
                  setIsOpen(false);
                }}
                className={`font-medium w-full px-3 py-2 text-left text-sm hover:bg-gray-100 cursor-pointer flex items-center justify-between first:rounded-t-md last:rounded-b-md ${
                  currency === curr.code
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700"
                }`}
              >
                <span>{curr.code}</span>
                <span className="text-gray-500">{curr.symbol}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useMapsLibrary } from "@vis.gl/react-google-maps";
import { useEffect, useState, useRef, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Loader2, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

const POPULAR_CITIES = [
  { name: "Hanoi", emoji: "🇻🇳" },
  { name: "Ho Chi Minh", emoji: "🇻🇳" },
  { name: "Da Nang", emoji: "🏖️" },
  { name: "Paris", emoji: "🗼" },
  { name: "Tokyo", emoji: "⛩️" },
  { name: "Bangkok", emoji: "🛕" },
  { name: "Seoul", emoji: "🇰🇷" },
  { name: "London", emoji: "💂" },
  { name: "New York", emoji: "🗽" },
  { name: "Rome", emoji: "🏛️" },
  { name: "Sydney", emoji: "🇦🇺" },
  { name: "Singapore", emoji: "🇸🇬" },
];

interface CityAutocompleteProps {
  value: string;
  onChange: (city: string) => void;
  placeholder?: string;
}

export default function CityAutocomplete({
  value,
  onChange,
  placeholder = "Search for a city...",
}: CityAutocompleteProps) {
  const placesLibrary = useMapsLibrary("places");
  const [placesService, setPlacesService] =
    useState<google.maps.places.AutocompleteService | null>(null);
  const [sessionToken, setSessionToken] =
    useState<google.maps.places.AutocompleteSessionToken | null>(null);

  const [inputValue, setInputValue] = useState(value);
  const [predictions, setPredictions] = useState<
    google.maps.places.AutocompletePrediction[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!placesLibrary) return;
    setPlacesService(new placesLibrary.AutocompleteService());
    setSessionToken(new placesLibrary.AutocompleteSessionToken());
  }, [placesLibrary]);

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  // Fetch city predictions
  useEffect(() => {
    if (!placesService || !inputValue.trim()) {
      setPredictions([]);
      return;
    }

    setIsLoading(true);

    const timer = setTimeout(() => {
      if (!placesService) return;

      placesService.getPlacePredictions(
        {
          input: inputValue,
          types: ["(cities)"],
          sessionToken: sessionToken ?? undefined,
        },
        (results, status) => {
          setIsLoading(false);
          if (status === google.maps.places.PlacesServiceStatus.OK && results) {
            setPredictions(results);
            setSelectedIndex(0);
          } else {
            setPredictions([]);
          }
        },
      );
    }, 400);

    return () => clearTimeout(timer);
  }, [inputValue, placesService, sessionToken]);

  // Close on outside click
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

  const handleSelect = useCallback(
    (city: string) => {
      onChange(city);
      setInputValue(city);
      setIsOpen(false);
      setPredictions([]);
    },
    [onChange],
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    setIsOpen(true);
  };

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) {
        if (e.key === "ArrowDown" || e.key === "Enter") {
          setIsOpen(true);
          return;
        }
        return;
      }

      const items =
        predictions.length > 0
          ? predictions.map((p) => p.structured_formatting.main_text)
          : inputValue.trim()
            ? []
            : POPULAR_CITIES.map((c) => c.name);

      if (items.length === 0) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev < items.length - 1 ? prev + 1 : prev,
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
          break;
        case "Enter":
          e.preventDefault();
          if (items[selectedIndex]) {
            handleSelect(items[selectedIndex]);
          }
          break;
        case "Escape":
          e.preventDefault();
          setIsOpen(false);
          break;
      }
    },
    [isOpen, predictions, inputValue, selectedIndex, handleSelect],
  );

  const showPopularCities = isOpen && !inputValue.trim();
  const showPredictions = isOpen && inputValue.trim() && predictions.length > 0;

  return (
    <div className="relative w-full" ref={containerRef}>
      <div className="relative">
        <Input
          ref={inputRef}
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pr-8 h-9 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Loader2 className="animate-spin h-3.5 w-3.5 text-gray-400" />
          </div>
        )}
      </div>

      {/* Popular cities dropdown */}
      {showPopularCities && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          <p className="px-3 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
            Popular cities
          </p>
          <div className="max-h-48 overflow-auto">
            {POPULAR_CITIES.map((city, index) => (
              <button
                key={city.name}
                type="button"
                className={cn(
                  "w-full px-3 py-2 flex items-center gap-2 text-sm transition-colors text-left",
                  index === selectedIndex
                    ? "bg-blue-50 text-blue-700"
                    : "hover:bg-gray-50",
                )}
                onClick={() => handleSelect(city.name)}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <span className="text-base">{city.emoji}</span>
                <span className="truncate">{city.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Search predictions dropdown */}
      {showPredictions && (
        <ul className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-auto">
          {predictions.map((prediction, index) => (
            <li
              key={prediction.place_id}
              className={cn(
                "px-3 py-2 cursor-pointer flex items-center gap-2 text-sm transition-colors",
                index === selectedIndex
                  ? "bg-blue-50 text-blue-700"
                  : "hover:bg-gray-50",
              )}
              onClick={() =>
                handleSelect(prediction.structured_formatting.main_text)
              }
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <MapPin
                className={cn(
                  "h-3.5 w-3.5 shrink-0",
                  index === selectedIndex ? "text-blue-500" : "text-gray-400",
                )}
              />
              <span className="truncate">{prediction.description}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

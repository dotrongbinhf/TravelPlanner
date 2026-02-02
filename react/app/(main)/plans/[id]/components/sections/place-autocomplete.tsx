"use client";

import { useMapsLibrary } from "@vis.gl/react-google-maps";
import { useEffect, useState, useRef, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Loader2, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

interface PlaceAutocompleteProps {
  onPlaceSelect: (
    prediction: google.maps.places.AutocompletePrediction,
  ) => void;
  onClose?: () => void;
}

export default function PlaceAutocomplete({
  onPlaceSelect,
  onClose,
}: PlaceAutocompleteProps) {
  const placesLibrary = useMapsLibrary("places");
  const [placesService, setPlacesService] =
    useState<google.maps.places.AutocompleteService | null>(null);
  const [sessionToken, setSessionToken] =
    useState<google.maps.places.AutocompleteSessionToken | null>(null);

  const [value, setValue] = useState("");
  const [predictions, setPredictions] = useState<
    google.maps.places.AutocompletePrediction[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!placesLibrary) return;
    setPlacesService(new placesLibrary.AutocompleteService());
    setSessionToken(new placesLibrary.AutocompleteSessionToken());
  }, [placesLibrary]);

  useEffect(() => {
    if (!placesService || !value) {
      setPredictions([]);
      return;
    }

    if (value === "") {
      setPredictions([]);
      return;
    }

    setIsLoading(true);

    const timer = setTimeout(() => {
      if (!placesService) return;

      const request = {
        input: value,
        sessionToken: sessionToken ?? undefined,
      };

      placesService.getPlacePredictions(request, (results, status) => {
        setIsLoading(false);
        if (status === google.maps.places.PlacesServiceStatus.OK && results) {
          setPredictions(results);
          setSelectedIndex(0); // Reset selection when predictions change
        } else {
          setPredictions([]);
        }
      });
    }, 500);

    return () => clearTimeout(timer);
  }, [value, placesService, sessionToken]);

  // Reset selection when predictions change
  useEffect(() => {
    setSelectedIndex(0);
  }, [predictions]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        onClose?.();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  const handleSelect = useCallback(
    (prediction: google.maps.places.AutocompletePrediction) => {
      onPlaceSelect(prediction);
      setValue("");
      setPredictions([]);
      onClose?.();
    },
    [onPlaceSelect, onClose],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (predictions.length === 0) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev < predictions.length - 1 ? prev + 1 : prev,
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
          break;
        case "Enter":
          e.preventDefault();
          if (predictions[selectedIndex]) {
            handleSelect(predictions[selectedIndex]);
          }
          break;
        case "Escape":
          e.preventDefault();
          onClose?.();
          break;
      }
    },
    [predictions, selectedIndex, handleSelect, onClose],
  );

  return (
    <div className="relative w-full" ref={containerRef}>
      <div className="relative">
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search for a place..."
          className="w-full pr-8 h-12 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          autoFocus
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Loader2 className="animate-spin h-4 w-4 text-gray-400" />
          </div>
        )}
      </div>

      {predictions.length > 0 && (
        <ul className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto">
          {predictions.map((prediction, index) => (
            <li
              key={prediction.place_id}
              className={cn(
                "px-4 py-3 cursor-pointer flex items-center gap-2 text-sm transition-colors",
                index === selectedIndex
                  ? "bg-blue-50 text-blue-700"
                  : "hover:bg-gray-100",
              )}
              onClick={() => handleSelect(prediction)}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <MapPin
                className={cn(
                  "h-4 w-4 shrink-0",
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

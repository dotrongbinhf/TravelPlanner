"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { Place } from "@/types/place";
import { ItineraryItem } from "@/types/itineraryItem";

interface SelectedPlaceState {
  placeId: string | null;
  place: Place | null;
  dayIndex: number | null;
  itemIndex: number | null;
  isFromItinerary: boolean;
  triggerSource?: "map" | "list";
}

interface ItineraryContextValue {
  // Selected place state
  selectedPlace: SelectedPlaceState;
  selectPlaceFromItinerary: (
    item: ItineraryItem,
    dayIndex: number,
    itemIndex: number,
    source?: "map" | "list",
  ) => void;
  selectPlaceFromMap: (placeId: string) => void;
  clearPlaceSelection: () => void;

  // Map display options
  showMarkers: boolean;
  setShowMarkers: (show: boolean) => void;
  filterMode: "all" | "byDay";
  setFilterMode: (mode: "all" | "byDay") => void;
  selectedDayIndex: number;
  setSelectedDayIndex: (index: number) => void;
}

const ItineraryContext = createContext<ItineraryContextValue | null>(null);

export function useItineraryContext() {
  const context = useContext(ItineraryContext);
  if (!context) {
    throw new Error(
      "useItineraryContext must be used within an ItineraryProvider",
    );
  }
  return context;
}

interface ItineraryProviderProps {
  children: ReactNode;
  totalDays: number;
}

export function ItineraryProvider({
  children,
  totalDays,
}: ItineraryProviderProps) {
  // Selected place state
  const [selectedPlace, setSelectedPlace] = useState<SelectedPlaceState>({
    placeId: null,
    place: null,
    dayIndex: null,
    itemIndex: null,
    isFromItinerary: false,
  });

  // Map display options
  const [showMarkers, setShowMarkers] = useState(true);
  const [filterMode, setFilterMode] = useState<"all" | "byDay">("byDay");
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);

  const handleSetShowMarkers = useCallback((show: boolean) => {
    setShowMarkers(show);
    if (!show) {
      setFilterMode("all");
    }
  }, []);

  const handleSetFilterMode = useCallback((mode: "all" | "byDay") => {
    setFilterMode(mode);
    if (mode === "byDay") {
      setShowMarkers(true);
    }
  }, []);

  const selectPlaceFromItinerary = useCallback(
    (
      item: ItineraryItem,
      dayIndex: number,
      itemIndex: number,
      source: "map" | "list" = "list",
    ) => {
      setSelectedPlace({
        placeId: item.place.placeId,
        place: item.place,
        dayIndex,
        itemIndex,
        isFromItinerary: true,
        triggerSource: source,
      });
      setSelectedDayIndex(dayIndex);

      if (!showMarkers) {
        setShowMarkers(true);
        setFilterMode("byDay");
      }
    },
    [showMarkers],
  );

  const selectPlaceFromMap = useCallback((placeId: string) => {
    setSelectedPlace({
      placeId,
      place: null,
      dayIndex: null,
      itemIndex: null,
      isFromItinerary: false,
    });
  }, []);

  const clearPlaceSelection = useCallback(() => {
    setSelectedPlace({
      placeId: null,
      place: null,
      dayIndex: null,
      itemIndex: null,
      isFromItinerary: false,
    });
  }, []);

  const value: ItineraryContextValue = {
    selectedPlace,
    selectPlaceFromItinerary,
    selectPlaceFromMap,
    clearPlaceSelection,
    showMarkers,
    setShowMarkers: handleSetShowMarkers,
    filterMode,
    setFilterMode: handleSetFilterMode,
    selectedDayIndex,
    setSelectedDayIndex,
  };

  return (
    <ItineraryContext.Provider value={value}>
      {children}
    </ItineraryContext.Provider>
  );
}

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

export interface ChatPlace {
  id: string; // unique widget item id
  placeId?: string; // google place id if available
  name: string;
  location: { lat: number; lng: number };
  source: "hotel" | "attraction" | "restaurant";
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

  // Chat place state
  chatPlaces: ChatPlace[];
  setChatPlaces: (places: ChatPlace[]) => void;
  selectedChatPlace: ChatPlace | null;
  setSelectedChatPlace: (place: ChatPlace | null) => void;

  // Map display options
  showMarkers: boolean;
  setShowMarkers: (show: boolean) => void;
  showDirections: boolean;
  setShowDirections: (show: boolean) => void;
  filterMode: "all" | "byDay";
  setFilterMode: (mode: "all" | "byDay") => void;
  selectedDayIndex: number;
  setSelectedDayIndex: (dayIndex: number) => void;

  // Widget → Map focus (direct coordinates)
  focusLocation: { lat: number; lng: number } | null;
  setFocusLocation: (loc: { lat: number; lng: number } | null) => void;
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

  // Chat place state
  const [chatPlaces, setChatPlaces] = useState<ChatPlace[]>([]);
  const [selectedChatPlace, setSelectedChatPlace] = useState<ChatPlace | null>(null);

  // Map display options
  const [filterMode, setFilterMode] = useState<"all" | "byDay">("byDay");
  const [showMarkers, setShowMarkers] = useState(true);
  const [showDirections, setShowDirections] = useState(false);
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);

  // Widget → Map focus location
  const [focusLocation, setFocusLocation] = useState<{ lat: number; lng: number } | null>(null);

  const handleSetShowMarkers = useCallback((show: boolean) => {
    setShowMarkers(show);
    if (!show) {
      setFilterMode("all");
    }
  }, []);

  const handleSetFilterMode = useCallback(
    (mode: "all" | "byDay") => {
      setFilterMode(mode);
      if (mode === "byDay" && !showDirections) {
        setShowMarkers(true);
      }
    },
    [showDirections],
  );

  const selectPlaceFromItinerary = useCallback(
    (
      item: ItineraryItem,
      dayIndex: number,
      itemIndex: number,
      source: "map" | "list" = "list",
    ) => {
      setSelectedPlace({
        placeId: item.place?.placeId ?? null,
        place: item.place ?? null,
        dayIndex,
        itemIndex,
        isFromItinerary: true,
        triggerSource: source,
      });
      setSelectedDayIndex(dayIndex);
      setSelectedChatPlace(null);

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
    setSelectedChatPlace(null);
  }, []);

  const clearPlaceSelection = useCallback(() => {
    setSelectedPlace({
      placeId: null,
      place: null,
      dayIndex: null,
      itemIndex: null,
      isFromItinerary: false,
    });
    setSelectedChatPlace(null);
  }, []);

  const value: ItineraryContextValue = {
    selectedPlace,
    selectPlaceFromItinerary,
    selectPlaceFromMap,
    clearPlaceSelection,
    chatPlaces,
    setChatPlaces,
    selectedChatPlace,
    setSelectedChatPlace,
    showMarkers,
    setShowMarkers: handleSetShowMarkers,
    showDirections,
    setShowDirections,
    filterMode,
    setFilterMode: handleSetFilterMode,
    selectedDayIndex,
    setSelectedDayIndex,
    focusLocation,
    setFocusLocation,
  };

  return (
    <ItineraryContext.Provider value={value}>
      {children}
    </ItineraryContext.Provider>
  );
}

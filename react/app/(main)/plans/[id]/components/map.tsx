"use client";

import { Map as GoogleMap, Marker, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState, useMemo, useCallback } from "react";
import PlaceDetailDialog from "./maps/place-detail-dialog";
import ItineraryMarker from "./maps/itinerary-marker";
import MapMenu from "./maps/map-menu";
import ItineraryDayNavigator from "./maps/itineraryDay-navigator";
import DirectionsRenderer from "./maps/directions-renderer";
import {
  getRouteBetweenTwoItems,
  getRoutesByDayId,
} from "@/api/itineraryItemsRoute/itineraryItemsRoute";

import { ItineraryItem } from "@/types/itineraryItem";
import { ItineraryItemsRoute } from "@/types/itineraryItemsRoute";
import { Plan } from "@/types/plan";
import { useItineraryContext } from "@/contexts/ItineraryContext";
import { getDayColor } from "@/constants/day-colors";
import { isCrossDayEvent } from "./sections/cross-day-utils";
import { generateGoogleMapsLink } from "@/utils/map";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface GoogleMapIntegrationProps {
  plan: Plan | null;
  onItineraryUpdate: (item: ItineraryItem) => void;
}

export default function GoogleMapIntegration({
  plan,
  onItineraryUpdate,
}: GoogleMapIntegrationProps) {
  const map = useMap("itinerary-map");
  const [center, setCenter] = useState<{ lat: number; lng: number }>();
  const [clickedPos, setClickedPos] = useState<
    google.maps.LatLng | google.maps.LatLngLiteral | null
  >(null);

  // State for routes
  const [routes, setRoutes] = useState<ItineraryItemsRoute[]>([]);
  const [connectionRoutes, setConnectionRoutes] = useState<
    ItineraryItemsRoute[]
  >([]);
  const [isRoutesLoading, setIsRoutesLoading] = useState(false);

  const {
    selectedPlace,
    selectPlaceFromItinerary,
    selectPlaceFromMap,
    clearPlaceSelection,
    showMarkers,
    setShowMarkers,
    showDirections,
    setShowDirections,
    filterMode,
    setFilterMode,
    selectedDayIndex,
    setSelectedDayIndex,
  } = useItineraryContext();

  const itineraryDays = plan?.itineraryDays ?? [];
  const totalDays = itineraryDays.length;

  // Prepare markers data from itinerary
  const markersData = useMemo(() => {
    const markers: Array<{
      item: ItineraryItem;
      dayIndex: number;
      itemIndex: number;
      totalItemsInDay: number;
      isBed: boolean;
      isOverallFirst: boolean;
      isOverallLast: boolean;
    }> = [];

    const sorted = [...itineraryDays].sort((a, b) => a.order - b.order);
    const totalDays = sorted.length;

    sorted.forEach((day, dayIndex) => {
      const sortedItems = [...(day.itineraryItems || [])].sort((a, b) =>
        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
      );
      const isLastDay = dayIndex === totalDays - 1;
      const isFirstDay = dayIndex === 0;

      sortedItems.forEach((item, itemIndex) => {
        const isLastInDay = itemIndex === sortedItems.length - 1;
        const isFirstInDay = itemIndex === 0;

        markers.push({
          item,
          dayIndex,
          itemIndex,
          totalItemsInDay: sortedItems.length,
          isBed:
            isLastInDay &&
            !isLastDay &&
            isCrossDayEvent(item.startTime, item.duration),
          isOverallFirst: isFirstDay && isFirstInDay,
          isOverallLast: isLastDay && isLastInDay,
        });
      });
    });

    return markers;
  }, [itineraryDays]);

  // Deduplicated markers for rendering
  const deduplicatedMarkers = useMemo(() => {
    // Track bed markers by placeId → keep earliest day's color
    const bedPlaceSeen: globalThis.Map<string, number> = new globalThis.Map(); // placeId → earliest dayIndex
    const result: typeof markersData = [];
    const skippedPlaceIds: globalThis.Set<string> = new globalThis.Set();

    // find all bed markers and track earliest day per placeId
    for (const m of markersData) {
      if (m.isBed) {
        const pid = m.item.place.placeId;
        if (!bedPlaceSeen.has(pid) || m.dayIndex < bedPlaceSeen.get(pid)!) {
          bedPlaceSeen.set(pid, m.dayIndex);
        }
      }
    }

    // for non-bed markers that are the first item of a day,
    const sorted = [...itineraryDays].sort((a, b) => a.order - b.order);
    for (const m of markersData) {
      if (m.itemIndex === 0 && m.dayIndex > 0) {
        const prevDay = sorted[m.dayIndex - 1];
        if (prevDay) {
          const prevItems = [...(prevDay.itineraryItems || [])].sort((a, b) =>
            (a.startTime ?? "").localeCompare(b.startTime ?? ""),
          );
          const lastOfPrev = prevItems[prevItems.length - 1];
          if (lastOfPrev && lastOfPrev.place.placeId === m.item.place.placeId) {
            // This first item is same place as prev day's last (bed) → skip
            skippedPlaceIds.add(`${m.dayIndex}-${m.item.place.placeId}`);
            continue;
          }
        }
      }

      // For bed markers with duplicate placeId, only keep the first occurrence
      if (m.isBed) {
        const pid = m.item.place.placeId;
        const earliestDay = bedPlaceSeen.get(pid);
        if (earliestDay !== undefined && m.dayIndex !== earliestDay) {
          // Check if there's already a bed marker for this place from earliest day
          const alreadyHasBed = result.some(
            (r) => r.isBed && r.item.place.placeId === pid,
          );
          if (alreadyHasBed) {
            continue; // Skip duplicate bed marker
          }
        }
      }

      result.push(m);
    }

    return result;
  }, [markersData, itineraryDays]);

  // Filter markers based on filter mode
  const visibleMarkers = useMemo(() => {
    if (!showMarkers) return [];
    if (filterMode === "all") return deduplicatedMarkers;

    // In byDay mode, show this day's markers PLUS cross-day markers from previous day
    const sorted = [...itineraryDays].sort((a, b) => a.order - b.order);
    const prevDay = selectedDayIndex > 0 ? sorted[selectedDayIndex - 1] : null;

    // Find the last item of the previous day that is a cross-day event
    let crossDayFromPrev: globalThis.Set<string> | null = null;
    if (prevDay) {
      const prevItems = [...(prevDay.itineraryItems || [])].sort((a, b) =>
        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
      );
      crossDayFromPrev = new globalThis.Set<string>();
      prevItems.forEach((item) => {
        if (isCrossDayEvent(item.startTime, item.duration)) {
          crossDayFromPrev!.add(item.id);
        }
      });
    }

    return deduplicatedMarkers.filter((m) => {
      // Include markers from the selected day
      if (m.dayIndex === selectedDayIndex) return true;
      // Include cross-day markers from previous day
      if (
        crossDayFromPrev &&
        m.dayIndex === selectedDayIndex - 1 &&
        crossDayFromPrev.has(m.item.id)
      ) {
        return true;
      }
      return false;
    });
  }, [
    deduplicatedMarkers,
    showMarkers,
    filterMode,
    selectedDayIndex,
    itineraryDays,
  ]);

  // Get visible items for directions (based on filter mode)
  const visibleItems = useMemo(() => {
    if (filterMode === "all") {
      return markersData.map((m) => m.item);
    }

    // In byDay mode, show this day's items PLUS cross-day items from previous day
    const sorted = [...itineraryDays].sort((a, b) => a.order - b.order);
    const prevDay = selectedDayIndex > 0 ? sorted[selectedDayIndex - 1] : null;

    let crossDayFromPrev: globalThis.Set<string> | null = null;
    if (prevDay) {
      const prevItems = [...(prevDay.itineraryItems || [])].sort((a, b) =>
        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
      );
      crossDayFromPrev = new globalThis.Set<string>();
      prevItems.forEach((item) => {
        if (isCrossDayEvent(item.startTime, item.duration)) {
          crossDayFromPrev!.add(item.id);
        }
      });
    }

    return markersData
      .filter((m) => {
        if (m.dayIndex === selectedDayIndex) return true;
        if (
          crossDayFromPrev &&
          m.dayIndex === selectedDayIndex - 1 &&
          crossDayFromPrev.has(m.item.id)
        ) {
          return true;
        }
        return false;
      })
      .map((m) => m.item);
  }, [markersData, filterMode, selectedDayIndex, itineraryDays]);

  // Fetch routes based on filterMode
  const fetchRoutes = useCallback(async () => {
    if (!showDirections || !itineraryDays.length) {
      setRoutes([]);
      return;
    }

    setIsRoutesLoading(true);

    try {
      if (filterMode === "all") {
        // Fetch routes for ALL days
        const allRoutes: ItineraryItemsRoute[] = [];
        for (const day of itineraryDays) {
          const dayRoutes = await getRoutesByDayId(day.id);
          allRoutes.push(...dayRoutes);
        }
        setRoutes(allRoutes);

        const allConnectionRoutes: ItineraryItemsRoute[] = [];
        for (let i = 0; i < itineraryDays.length - 1; i++) {
          const currentDay = itineraryDays[i];
          const nextDay = itineraryDays[i + 1];
          const lastItemOfCurrentDay =
            currentDay.itineraryItems?.[currentDay.itineraryItems.length - 1];
          const firstItemOfNextDay = nextDay.itineraryItems?.[0];
          if (
            lastItemOfCurrentDay &&
            firstItemOfNextDay &&
            lastItemOfCurrentDay.place.id !== firstItemOfNextDay.place.id
          ) {
            const connectionRoute = await getRouteBetweenTwoItems(
              lastItemOfCurrentDay.id,
              firstItemOfNextDay.id,
            );
            allConnectionRoutes.push(connectionRoute);
          }
        }
        setConnectionRoutes(allConnectionRoutes);
      } else {
        // Fetch routes for current day only
        const currentDay = itineraryDays.find(
          (d) => d.order === selectedDayIndex,
        );
        if (!currentDay) {
          setRoutes([]);
          return;
        }
        const fetchedRoutes = await getRoutesByDayId(currentDay.id);
        setRoutes(fetchedRoutes);
      }
    } catch (error) {
      console.error("Failed to fetch routes:", error);
      setRoutes([]);
    } finally {
      setIsRoutesLoading(false);
    }
  }, [showDirections, itineraryDays, selectedDayIndex, filterMode]);

  // Fetch routes when showDirections, selectedDayIndex, or filterMode changes
  useEffect(() => {
    fetchRoutes();
  }, [fetchRoutes]);

  // Center map when selectedPlace changes
  useEffect(() => {
    if (!map) return;
    if (
      selectedPlace.placeId &&
      selectedPlace.isFromItinerary &&
      selectedPlace.place?.location?.coordinates
    ) {
      const lat = selectedPlace.place.location.coordinates[1];
      const lng = selectedPlace.place.location.coordinates[0];
      map.panTo({ lat: lat - 0.0025, lng: lng });
      map.setZoom(16);
    } else {
      map.setZoom(15);
    }
  }, [selectedPlace, map]);

  useEffect(() => {
    if (!map) return;
    if (clickedPos) {
      map.panTo({
        lat: parseFloat(clickedPos.lat.toString()) - 0.0025,
        lng: parseFloat(clickedPos.lng.toString()),
      });
      map.setZoom(16);
    } else {
      map.setZoom(15);
    }
  }, [clickedPos, map]);

  // Set Initial Map Center
  useEffect(() => {
    // Set initial center based on first itinerary place or default
    if (markersData.length > 0) {
      const firstPlace = markersData[0].item.place;
      if (firstPlace?.location?.coordinates) {
        setCenter({
          lat: firstPlace.location.coordinates[1],
          lng: firstPlace.location.coordinates[0],
        });
        return;
      }
    }

    // Somewhere in middle of Hanoi
    setCenter({
      lat: 21.02955,
      lng: 105.83582,
    });
  }, [markersData]);

  const handleMapClick = (e: any) => {
    if (e.detail?.placeId) {
      console.log("Clicked POI:", e.detail.placeId);
      e.stop?.();
      selectPlaceFromMap(e.detail.placeId);
      setClickedPos(e.detail.latLng ?? null);
    } else {
      clearPlaceSelection();
      setClickedPos(null);
    }
  };

  const handlePlaceDialogClose = () => {
    clearPlaceSelection();
    setClickedPos(null);
  };

  return (
    <div className="w-full h-full flex items-center justify-center rounded-lg shadow-sm border-2 border-gray-200 overflow-hidden relative">
      {center && (
        <GoogleMap
          id="itinerary-map" // useMap
          defaultZoom={15}
          defaultCenter={{ lat: center.lat, lng: center.lng }}
          gestureHandling={"greedy"}
          disableDefaultUI={true}
          mapId="itinerary-map"
          onClick={handleMapClick}
        >
          {/* POI click marker */}
          {selectedPlace.placeId &&
            clickedPos &&
            !selectedPlace.isFromItinerary && <Marker position={clickedPos} />}

          {/* Itinerary Markers */}
          {visibleMarkers.map((marker) => {
            const {
              item,
              dayIndex,
              itemIndex,
              totalItemsInDay,
              isBed,
              isOverallFirst,
              isOverallLast,
            } = marker;
            const place = item.place;

            if (!place?.location?.coordinates) return null;

            const position = {
              lat: place.location.coordinates[1],
              lng: place.location.coordinates[0],
            };

            return (
              <ItineraryMarker
                key={`${item.id}-${dayIndex}-${isBed ? "bed" : itemIndex}`}
                position={position}
                orderNumber={itemIndex + 1}
                dayColor={getDayColor(dayIndex)}
                isFirst={isOverallFirst}
                isLast={isOverallLast}
                isBed={isBed}
                isActive={
                  selectedPlace.placeId === place.placeId &&
                  (selectedPlace.dayIndex === dayIndex ||
                    selectedPlace.dayIndex === selectedDayIndex)
                }
                onClick={() => {
                  // For cross-day markers from previous day, stay on current day
                  const clickDayIndex =
                    filterMode === "byDay" && dayIndex !== selectedDayIndex
                      ? selectedDayIndex
                      : dayIndex;
                  selectPlaceFromItinerary(
                    item,
                    clickDayIndex,
                    itemIndex,
                    "map",
                  );
                }}
              />
            );
          })}

          {/* Directions Renderer */}
          {showDirections &&
            filterMode === "byDay" &&
            visibleItems.length >= 2 && (
              <DirectionsRenderer
                items={visibleItems}
                existingRoutes={routes}
                onRoutesChange={fetchRoutes}
                routeColor={getDayColor(selectedDayIndex)}
              />
            )}

          {/* Multi-Day Directions */}
          {showDirections &&
            filterMode === "all" &&
            itineraryDays.length > 0 && (
              <>
                {/* Render directions for each day */}
                {itineraryDays
                  .sort((a, b) => a.order - b.order)
                  .map((day, dayIndex) => {
                    const dayItems = (day.itineraryItems || [])
                      .slice()
                      .sort((a, b) =>
                        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
                      );

                    if (dayItems.length < 2) return null;

                    // Get routes for this day - check both start and end item IDs
                    const dayItemIds = new Set(dayItems.map((item) => item.id));
                    const dayRoutes = routes.filter(
                      (r) =>
                        dayItemIds.has(r.startItineraryItemId) &&
                        dayItemIds.has(r.endItineraryItemId),
                    );

                    return (
                      <DirectionsRenderer
                        key={`day-${day.id}`}
                        items={dayItems}
                        existingRoutes={dayRoutes}
                        onRoutesChange={fetchRoutes}
                        routeColor={getDayColor(dayIndex)}
                      />
                    );
                  })}

                {/* Render connections between days (if last item of day N != first item of day N+1) */}
                {itineraryDays
                  .sort((a, b) => a.order - b.order)
                  .slice(0, -1) // All days except last
                  .map((day, dayIndex) => {
                    const nextDay = itineraryDays.find(
                      (d) => d.order === day.order + 1,
                    );
                    if (!nextDay) return null;

                    const currentDayItems = (day.itineraryItems || [])
                      .slice()
                      .sort((a, b) =>
                        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
                      );
                    const nextDayItems = (nextDay.itineraryItems || [])
                      .slice()
                      .sort((a, b) =>
                        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
                      );

                    if (
                      currentDayItems.length === 0 ||
                      nextDayItems.length === 0
                    )
                      return null;

                    const lastItemOfCurrentDay =
                      currentDayItems[currentDayItems.length - 1];
                    const firstItemOfNextDay = nextDayItems[0];

                    // Skip if same place (e.g. same hotel)
                    if (
                      lastItemOfCurrentDay.place.placeId ===
                      firstItemOfNextDay.place.placeId
                    ) {
                      return null;
                    }

                    // Create connection items
                    const connectionItems = [
                      lastItemOfCurrentDay,
                      firstItemOfNextDay,
                    ];

                    // Find routes for this connection
                    const existingConnectionRoutes = connectionRoutes.filter(
                      (r) =>
                        r.startItineraryItemId === lastItemOfCurrentDay.id &&
                        r.endItineraryItemId === firstItemOfNextDay.id,
                    );

                    return (
                      <DirectionsRenderer
                        key={`connection-${day.id}-${nextDay.id}`}
                        items={connectionItems}
                        existingRoutes={existingConnectionRoutes}
                        onRoutesChange={fetchRoutes}
                        routeColor="#9CA3AF" // Gray color for connections
                        preserveOrder={true} // Keep order: lastItem of day N -> firstItem of day N+1
                      />
                    );
                  })}
              </>
            )}
        </GoogleMap>
      )}

      {/* Map Controls Container */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 pointer-events-none">
        <div className="pointer-events-auto">
          <MapMenu
            showMarkers={showMarkers}
            setShowMarkers={setShowMarkers}
            showDirections={showDirections}
            setShowDirections={setShowDirections}
            filterMode={filterMode}
            setFilterMode={setFilterMode}
          />
        </div>

        {/* Day Navigator (visible below menu when byDay mode is active) */}
        {filterMode === "byDay" && totalDays > 0 && (
          <div className="pointer-events-auto relative flex items-center justify-center">
            <ItineraryDayNavigator
              currentDay={selectedDayIndex}
              totalDays={totalDays}
              onPrevious={() => {
                const newDayIndex = Math.max(0, selectedDayIndex - 1);
                clearPlaceSelection();
                setSelectedDayIndex(newDayIndex);
                // Center on first item of new day
                const dayMarkers = markersData.filter(
                  (m) => m.dayIndex === newDayIndex,
                );
                if (dayMarkers.length > 0 && map) {
                  const firstItem = dayMarkers[0].item;
                  if (firstItem.place?.location?.coordinates) {
                    map.panTo({
                      lat: firstItem.place.location.coordinates[1] - 0.0025,
                      lng: firstItem.place.location.coordinates[0],
                    });
                  }
                }
              }}
              onNext={() => {
                const newDayIndex = Math.min(
                  totalDays - 1,
                  selectedDayIndex + 1,
                );
                clearPlaceSelection();
                setSelectedDayIndex(newDayIndex);
                // Center on first item of new day
                const dayMarkers = markersData.filter(
                  (m) => m.dayIndex === newDayIndex,
                );
                if (dayMarkers.length > 0 && map) {
                  const firstItem = dayMarkers[0].item;
                  if (firstItem.place?.location?.coordinates) {
                    map.panTo({
                      lat: firstItem.place.location.coordinates[1] - 0.0025,
                      lng: firstItem.place.location.coordinates[0],
                    });
                  }
                }
              }}
            />

            {visibleItems.length >= 2 && (
              <div className="absolute left-[calc(100%+8px)] top-0 h-full flex items-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-9 px-0 w-9 bg-white/95 backdrop-blur-sm rounded-full shadow-lg border border-gray-200 hover:bg-gray-100 flex items-center gap-1 text-sm font-semibold text-gray-700"
                        onClick={() => {
                          const link = generateGoogleMapsLink(
                            visibleItems,
                            routes,
                            "driving",
                          );
                          if (link) {
                            window.open(link, "_blank");
                          }
                        }}
                      >
                        <Image
                          src="/images/plans/google-maps.png"
                          alt="Google Maps"
                          width={16}
                          height={16}
                          className="object-contain"
                        />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Open in Google Maps</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            )}
          </div>
        )}

        {/* All Days Badge */}
        {filterMode === "all" &&
          (showMarkers || showDirections) &&
          totalDays > 0 && (
            <div className="pointer-events-auto flex items-center justify-center bg-white/95 backdrop-blur-sm rounded-full shadow-lg px-4 py-2 border border-gray-200">
              <span className="text-sm font-semibold text-gray-700">
                All Days
              </span>
            </div>
          )}
      </div>

      {/* Place Detail Dialog */}
      {selectedPlace.placeId && (
        <PlaceDetailDialog
          placeId={selectedPlace.placeId}
          existingPlace={selectedPlace.place}
          hideAddButton={selectedPlace.isFromItinerary}
          onClose={handlePlaceDialogClose}
          plan={plan}
          onAddItem={onItineraryUpdate}
        />
      )}
    </div>
  );
}

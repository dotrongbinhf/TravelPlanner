"use client";

import { Map, Marker, useMap } from "@vis.gl/react-google-maps";
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
    }> = [];

    itineraryDays
      .sort((a, b) => a.order - b.order)
      .forEach((day, dayIndex) => {
        const sortedItems = [...(day.itineraryItems || [])].sort((a, b) =>
          (a.startTime ?? "").localeCompare(b.startTime ?? ""),
        );

        sortedItems.forEach((item, itemIndex) => {
          markers.push({
            item,
            dayIndex,
            itemIndex,
            totalItemsInDay: sortedItems.length,
          });
        });
      });

    return markers;
  }, [itineraryDays]);

  // Filter markers based on filter mode
  const visibleMarkers = useMemo(() => {
    if (!showMarkers) return [];
    if (filterMode === "all") return markersData;
    return markersData.filter((m) => m.dayIndex === selectedDayIndex);
  }, [markersData, showMarkers, filterMode, selectedDayIndex]);

  // Get visible items for directions (based on filter mode)
  const visibleItems = useMemo(() => {
    if (filterMode === "all") {
      return markersData.map((m) => m.item);
    }
    return markersData
      .filter((m) => m.dayIndex === selectedDayIndex)
      .map((m) => m.item);
  }, [markersData, filterMode, selectedDayIndex]);

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
        <Map
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
            const { item, dayIndex, itemIndex, totalItemsInDay } = marker;
            const place = item.place;

            if (!place?.location?.coordinates) return null;

            const position = {
              lat: place.location.coordinates[1],
              lng: place.location.coordinates[0],
            };

            return (
              <ItineraryMarker
                key={item.id}
                position={position}
                orderNumber={itemIndex + 1}
                dayColor={getDayColor(dayIndex)}
                isFirst={itemIndex === 0}
                isLast={itemIndex === totalItemsInDay - 1}
                isActive={
                  selectedPlace.placeId === place.placeId &&
                  selectedPlace.dayIndex === dayIndex
                }
                onClick={() =>
                  selectPlaceFromItinerary(item, dayIndex, itemIndex, "map")
                }
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
        </Map>
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
          <div className="pointer-events-auto">
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

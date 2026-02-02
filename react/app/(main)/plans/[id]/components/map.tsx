"use client";

import { Map, Marker, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState, useMemo } from "react";
import PlaceDetailDialog from "./maps/place-detail-dialog";
import ItineraryMarker from "./maps/itinerary-marker";
import MapMenu from "./maps/map-menu";
import ItineraryDayNavigator from "./maps/itineraryDay-navigator";
import { useItineraryContext } from "../../../../../contexts/ItineraryContext";
import { getDayColor } from "../../../../../constants/day-colors";

import { ItineraryItem } from "@/types/itineraryItem";
import { Plan } from "@/types/plan";

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

  const {
    selectedPlace,
    selectPlaceFromItinerary,
    selectPlaceFromMap,
    clearPlaceSelection,
    showMarkers,
    setShowMarkers,
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
        </Map>
      )}

      {/* Map Controls Container */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 pointer-events-none">
        <div className="pointer-events-auto">
          <MapMenu
            showMarkers={showMarkers}
            setShowMarkers={setShowMarkers}
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

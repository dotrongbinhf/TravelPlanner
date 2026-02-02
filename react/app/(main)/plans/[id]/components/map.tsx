"use client";

import { Map, Marker } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";
import PlaceDetailDialog from "./place-detail-dialog";

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
  const [center, setCenter] = useState<{ lat: number; lng: number }>();
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);
  const [clickedPos, setClickedPos] = useState<
    google.maps.LatLng | google.maps.LatLngLiteral | null
  >(null);

  useEffect(() => {
    // navigator.geolocation.getCurrentPosition((position) => {
    //   setCenter({
    //     lat: position.coords.latitude,
    //     lng: position.coords.longitude,
    //   });
    // });
    setCenter({
      lat: 21.02955,
      lng: 105.83582,
    });
  }, []);

  return (
    <div className="w-full h-full flex items-center justify-center rounded-lg shadow-sm border-2 border-gray-200 overflow-hidden relative">
      {center && (
        <Map
          defaultZoom={15}
          defaultCenter={{ lat: center.lat, lng: center.lng }}
          gestureHandling={"greedy"}
          disableDefaultUI={true}
          onClick={(e) => {
            if (e.detail.placeId) {
              console.log("Clicked POI:", e.detail.placeId);
              e.stop(); // Prevent default InfoWindow
              setSelectedPlaceId(e.detail.placeId);
              setClickedPos(e.detail.latLng); // Store position
            } else {
              // Close info window if clicking elsewhere on map
              setSelectedPlaceId(null);
              setClickedPos(null);
            }
          }}
        >
          {selectedPlaceId && clickedPos && <Marker position={clickedPos} />}
        </Map>
      )}

      {selectedPlaceId && (
        <PlaceDetailDialog
          placeId={selectedPlaceId}
          onClose={() => {
            setSelectedPlaceId(null);
            setClickedPos(null);
          }}
          plan={plan}
          onAddItem={onItineraryUpdate}
        />
      )}
    </div>
  );
}

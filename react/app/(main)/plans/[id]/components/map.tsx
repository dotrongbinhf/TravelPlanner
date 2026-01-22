"use client";

import { APIProvider, Map } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

export default function GoogleMapIntegration() {
  const [center, setCenter] = useState<{ lat: number; lng: number }>();

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
    <div className="w-full h-full flex items-center justify-center rounded-lg shadow-sm border-2 border-gray-200 overflow-hidden">
      <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? ""}>
        {center && (
          <Map
            defaultZoom={15}
            defaultCenter={{ lat: center.lat, lng: center.lng }}
            gestureHandling={"greedy"}
            disableDefaultUI={true}
          />
        )}
      </APIProvider>
    </div>
  );
}

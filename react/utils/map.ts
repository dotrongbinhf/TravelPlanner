import { ItineraryItem } from "@/types/itineraryItem";
import { ItineraryItemsRoute } from "@/types/itineraryItemsRoute";

export function generateGoogleMapsLink(
  items: ItineraryItem[],
  existingRoutes: ItineraryItemsRoute[],
  travelMode: string = "driving",
): string {
  if (!items || items.length < 2) return "";

  const originItem = items[0];
  const destinationItem = items[items.length - 1];

  const originCoords = originItem.place?.location?.coordinates;
  const destCoords = destinationItem.place?.location?.coordinates;

  if (!originCoords || !destCoords) return "";

  // Origin and destination as lat,lng strings
  const origin = `${originCoords[1]},${originCoords[0]}`;
  const destination = `${destCoords[1]},${destCoords[0]}`;

  // 2. Build via waypoints using custom routes between places and intermediate places
  const waypointsList: string[] = [];

  for (let i = 0; i < items.length - 1; i++) {
    const startItem = items[i];
    const endItem = items[i + 1];

    // Find custom waypoints for this segment from existingRoutes
    const route = existingRoutes.find(
      (r) =>
        r.startItineraryItemId === startItem.id &&
        r.endItineraryItemId === endItem.id,
    );

    const customWaypoints = route?.waypoints ?? [];

    // Add custom waypoints
    customWaypoints
      .sort((a, b) => a.order - b.order)
      .forEach((wp) => {
        waypointsList.push(`${wp.lat},${wp.lng}`);
      });

    // Add the next place as a waypoint (if it's not the final destination)
    // Exception: If the final destination is an overnight place starting today, it's NOT the end of today's map route if there's no destination AFTER it.
    // However, the destination parameter handles the final point. So we only add waypoints for intermediate stops.
    if (i < items.length - 2) {
      const nextPlaceCoords = endItem.place?.location?.coordinates;
      if (nextPlaceCoords) {
        waypointsList.push(`${nextPlaceCoords[1]},${nextPlaceCoords[0]}`);
      }
    }
  }

  // 3. Construct the Google Maps URL
  const baseUrl = "https://www.google.com/maps/dir/?api=1";
  const params = new URLSearchParams();

  params.append("origin", origin);
  params.append("destination", destination);

  if (waypointsList.length > 0) {
    params.append("waypoints", waypointsList.join("|"));
  }

  params.append("travelmode", travelMode);

  return `${baseUrl}&${params.toString()}`;
}

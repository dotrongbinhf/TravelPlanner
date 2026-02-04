"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useMap, useMapsLibrary } from "@vis.gl/react-google-maps";
import { ItineraryItem } from "@/types/itineraryItem";
import {
  ItineraryItemsRoute,
  RouteWaypoint,
} from "@/types/itineraryItemsRoute";
import { upsertRoute } from "@/api/itineraryItemsRoute/itineraryItemsRoute";
import { UpdateRouteWaypointInput } from "@/api/itineraryItemsRoute/types";
import toast from "react-hot-toast";

interface DirectionsRendererProps {
  items: ItineraryItem[];
  existingRoutes: ItineraryItemsRoute[];
  onRoutesChange?: () => void;
  travelMode?: google.maps.TravelMode;
  routeColor?: string; // Optional color for the route
  preserveOrder?: boolean; // If true, don't sort items - keep original order
}

// Mapping structure to track which waypoints belong to which segment
interface WaypointSegmentMapping {
  segmentIndex: number;
  startItemId: string;
  endItemId: string;
  waypointStartIndex: number; // Index in the full waypoints array where this segment's custom waypoints start
  waypointCount: number; // Number of custom waypoints in this segment
}

// Store state for waypoint markers per segment
interface SegmentMarkerState {
  startItemId: string;
  endItemId: string;
  markers: google.maps.Marker[];
  currentWaypoints: RouteWaypoint[];
}

// Default route color
const DEFAULT_ROUTE_COLOR = "#4285F4";

export default function DirectionsRenderer({
  items,
  existingRoutes,
  onRoutesChange,
  travelMode = google.maps.TravelMode.DRIVING,
  routeColor = DEFAULT_ROUTE_COLOR,
  preserveOrder = false,
}: DirectionsRendererProps) {
  const map = useMap("itinerary-map");
  const routesLibrary = useMapsLibrary("routes");

  const [directionsService, setDirectionsService] =
    useState<google.maps.DirectionsService | null>(null);

  // Single renderer for this route
  const rendererRef = useRef<google.maps.DirectionsRenderer | null>(null);

  // Store marker states per segment
  const segmentMarkersRef = useRef<Map<string, SegmentMarkerState>>(new Map());

  // Track saving state
  const isSavingRef = useRef<Set<string>>(new Set());

  // Track when a custom waypoint marker is being dragged
  const isDraggingMarkerRef = useRef<boolean>(false);

  // Track when we're making programmatic changes (delete/drag waypoint)
  // to prevent directions_changed from recreating waypoints
  const isProgrammaticChangeRef = useRef<boolean>(false);

  // Store the current sorted items for reference
  const sortedItemsRef = useRef<ItineraryItem[]>([]);

  // Store segment mappings for directions_changed handler
  const segmentMappingsRef = useRef<WaypointSegmentMapping[]>([]);

  // Cache key for last calculated route to prevent unnecessary recalculations
  const lastCalculatedKeyRef = useRef<string>("");

  // Store dashed lines connecting route to exact location
  const connectorLinesRef = useRef<google.maps.Polyline[]>([]);

  // Initialize DirectionsService
  useEffect(() => {
    if (!routesLibrary) return;
    setDirectionsService(new routesLibrary.DirectionsService());
  }, [routesLibrary]);

  // Create a unique key for a segment
  const getSegmentKey = useCallback(
    (startItemId: string, endItemId: string) => `${startItemId}->${endItemId}`,
    [],
  );

  // Find existing route for a segment
  const findExistingRoute = useCallback(
    (startItemId: string, endItemId: string) => {
      return existingRoutes.find(
        (r) =>
          r.startItineraryItemId === startItemId &&
          r.endItineraryItemId === endItemId,
      );
    },
    [existingRoutes],
  );

  // Save waypoints for a segment
  const saveWaypoints = useCallback(
    async (
      startItemId: string,
      endItemId: string,
      waypoints: UpdateRouteWaypointInput[],
    ) => {
      const segmentKey = getSegmentKey(startItemId, endItemId);

      // Prevent duplicate saves
      if (isSavingRef.current.has(segmentKey)) return;

      isSavingRef.current.add(segmentKey);

      try {
        await upsertRoute({
          startItineraryItemId: startItemId,
          endItineraryItemId: endItemId,
          waypoints,
        });
        toast.success("Waypoints Saved");
      } catch (error) {
        console.error("Failed to save waypoints:", error);
        toast.error("Failed to save waypoints");
      } finally {
        isSavingRef.current.delete(segmentKey);
      }
    },
    [getSegmentKey],
  );

  // Sorted items - memoized (preserve order if specified)
  const sortedItems = useMemo(() => {
    if (preserveOrder) {
      return [...items]; // Keep original order
    }
    return [...items].sort((a, b) =>
      (a.startTime ?? "").localeCompare(b.startTime ?? ""),
    );
  }, [items, preserveOrder]);

  // Update ref when sortedItems changes
  useEffect(() => {
    sortedItemsRef.current = sortedItems;
  }, [sortedItems]);

  // Build all waypoints for single request
  const buildWaypointsForRequest = useCallback(() => {
    if (sortedItems.length < 2) return { waypoints: [], mappings: [] };

    const allWaypoints: google.maps.DirectionsWaypoint[] = [];
    const mappings: WaypointSegmentMapping[] = [];

    for (let i = 0; i < sortedItems.length - 1; i++) {
      const startItem = sortedItems[i];
      const endItem = sortedItems[i + 1];

      // Find custom waypoints for this segment
      const existingRoute = findExistingRoute(startItem.id, endItem.id);
      const customWaypoints = existingRoute?.waypoints ?? [];

      // Store mapping info
      mappings.push({
        segmentIndex: i,
        startItemId: startItem.id,
        endItemId: endItem.id,
        waypointStartIndex: allWaypoints.length,
        waypointCount: customWaypoints.length,
      });

      // Add custom waypoints as via points (stopover: false)
      customWaypoints
        .sort((a, b) => a.order - b.order)
        .forEach((wp) => {
          allWaypoints.push({
            location: new google.maps.LatLng(wp.lat, wp.lng),
            stopover: false,
          });
        });

      // Add next item as stopover (except for last item - that's the destination)
      if (i < sortedItems.length - 2) {
        const nextItemCoords = sortedItems[i + 1].place?.location?.coordinates;
        if (nextItemCoords) {
          allWaypoints.push({
            location: new google.maps.LatLng(
              nextItemCoords[1],
              nextItemCoords[0],
            ),
            stopover: true,
          });
        }
      }
    }

    return { waypoints: allWaypoints, mappings };
  }, [sortedItems, findExistingRoute]);

  // Build waypoints from LOCAL state (segmentMarkersRef) - used after delete/drag
  const buildWaypointsFromLocalState = useCallback(() => {
    if (sortedItems.length < 2) return { waypoints: [], mappings: [] };

    const allWaypoints: google.maps.DirectionsWaypoint[] = [];
    const mappings: WaypointSegmentMapping[] = [];

    for (let i = 0; i < sortedItems.length - 1; i++) {
      const startItem = sortedItems[i];
      const endItem = sortedItems[i + 1];
      const segmentKey = getSegmentKey(startItem.id, endItem.id);

      // Get custom waypoints from LOCAL state (not from props!)
      const segmentState = segmentMarkersRef.current.get(segmentKey);
      const customWaypoints = segmentState?.currentWaypoints ?? [];

      // Store mapping info
      mappings.push({
        segmentIndex: i,
        startItemId: startItem.id,
        endItemId: endItem.id,
        waypointStartIndex: allWaypoints.length,
        waypointCount: customWaypoints.length,
      });

      // Add custom waypoints as via points (stopover: false)
      customWaypoints
        .sort((a, b) => a.order - b.order)
        .forEach((wp) => {
          allWaypoints.push({
            location: new google.maps.LatLng(wp.lat, wp.lng),
            stopover: false,
          });
        });

      // Add next item as stopover (except for last item - that's the destination)
      if (i < sortedItems.length - 2) {
        const nextItemCoords = sortedItems[i + 1].place?.location?.coordinates;
        if (nextItemCoords) {
          allWaypoints.push({
            location: new google.maps.LatLng(
              nextItemCoords[1],
              nextItemCoords[0],
            ),
            stopover: true,
          });
        }
      }
    }

    return { waypoints: allWaypoints, mappings };
  }, [sortedItems, getSegmentKey]);

  // Create waypoint marker for a segment
  const createWaypointMarker = useCallback(
    (
      waypoint: RouteWaypoint,
      segmentKey: string,
      startItem: ItineraryItem,
      endItem: ItineraryItem,
    ): google.maps.Marker | null => {
      if (!map) return null;

      const marker = new google.maps.Marker({
        position: { lat: waypoint.lat, lng: waypoint.lng },
        map,
        draggable: true,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 4,
          fillColor: "#ffffff",
          fillOpacity: 1,
          strokeColor: "#000000",
          strokeWeight: 2,
        },
        title: "Drag to move, double-click to delete",
        cursor: "grab",
      });

      // Handle drag start
      marker.addListener("dragstart", () => {
        isDraggingMarkerRef.current = true;
      });

      // Handle drag end - save final position
      marker.addListener("dragend", () => {
        isDraggingMarkerRef.current = false;

        // Set flag to prevent directions_changed issues
        isProgrammaticChangeRef.current = true;

        const newPosition = marker.getPosition();
        if (!newPosition) {
          isProgrammaticChangeRef.current = false;
          return;
        }

        const segmentState = segmentMarkersRef.current.get(segmentKey);
        if (!segmentState) {
          isProgrammaticChangeRef.current = false;
          return;
        }

        const updatedWaypoints = segmentState.currentWaypoints.map((wp) =>
          wp.id === waypoint.id
            ? { ...wp, lat: newPosition.lat(), lng: newPosition.lng() }
            : wp,
        );

        // Update segment state
        segmentState.currentWaypoints = updatedWaypoints;

        // Save to backend
        saveWaypoints(
          startItem.id,
          endItem.id,
          updatedWaypoints.map((wp) => ({
            lat: wp.lat,
            lng: wp.lng,
            order: wp.order,
          })),
        );

        // Trigger refetch to sync with backend, then reset flag
        setTimeout(() => {
          onRoutesChange?.();
          setTimeout(() => {
            isProgrammaticChangeRef.current = false;
          }, 500);
        }, 50);
      });

      // Handle double-click - delete waypoint
      marker.addListener("dblclick", (e: google.maps.MapMouseEvent) => {
        // Stop event propagation to prevent other handlers
        if (e.stop) e.stop();

        // Set flag to prevent directions_changed from recreating waypoints
        isProgrammaticChangeRef.current = true;

        const segmentState = segmentMarkersRef.current.get(segmentKey);
        if (!segmentState) {
          isProgrammaticChangeRef.current = false;
          return;
        }

        const updatedWaypoints = segmentState.currentWaypoints
          .filter((wp) => wp.id !== waypoint.id)
          .map((wp, index) => ({ ...wp, order: index }));

        // Remove marker from map
        marker.setMap(null);

        // Update segment state
        segmentState.markers = segmentState.markers.filter((m) => m !== marker);
        segmentState.currentWaypoints = updatedWaypoints;

        // Save to backend (without triggering refetch)
        saveWaypoints(
          startItem.id,
          endItem.id,
          updatedWaypoints.map((wp) => ({
            lat: wp.lat,
            lng: wp.lng,
            order: wp.order,
          })),
        );

        setTimeout(() => {
          onRoutesChange?.();
          // Reset flag after route recalculates (allow time for recalculation)
          setTimeout(() => {
            isProgrammaticChangeRef.current = false;
          }, 500);
        }, 50);
      });

      return marker;
    },
    [map, saveWaypoints, onRoutesChange, routeColor],
  );

  // Create markers for all segments
  const createAllMarkers = useCallback(() => {
    // Clean up existing markers
    segmentMarkersRef.current.forEach((state) => {
      state.markers.forEach((m) => m.setMap(null));
    });
    segmentMarkersRef.current.clear();

    if (sortedItems.length < 2) return;

    for (let i = 0; i < sortedItems.length - 1; i++) {
      const startItem = sortedItems[i];
      const endItem = sortedItems[i + 1];
      const segmentKey = getSegmentKey(startItem.id, endItem.id);

      const existingRoute = findExistingRoute(startItem.id, endItem.id);
      const customWaypoints = existingRoute?.waypoints ?? [];

      const markers = customWaypoints
        .map((wp) => createWaypointMarker(wp, segmentKey, startItem, endItem))
        .filter((m): m is google.maps.Marker => m !== null);

      segmentMarkersRef.current.set(segmentKey, {
        startItemId: startItem.id,
        endItemId: endItem.id,
        markers,
        currentWaypoints: customWaypoints,
      });
    }
  }, [sortedItems, getSegmentKey, findExistingRoute, createWaypointMarker]);

  // Draw lines from route snap points to exact item locations
  const drawConnectorLines = useCallback(
    (result: google.maps.DirectionsResult) => {
      // Clear existing lines
      connectorLinesRef.current.forEach((line) => line.setMap(null));
      connectorLinesRef.current = [];

      if (!map || !result.routes[0] || !result.routes[0].legs) return;

      const legs = result.routes[0].legs;

      sortedItems.forEach((item, index) => {
        if (!item.place?.location?.coordinates) return;
        const itemLat = item.place.location.coordinates[1];
        const itemLng = item.place.location.coordinates[0];
        const itemLoc = new google.maps.LatLng(itemLat, itemLng);

        // Find the corresponding point on the route
        let routePoint: google.maps.LatLng | null = null;

        if (index === 0) {
          if (legs.length > 0) routePoint = legs[0].start_location;
        } else if (index === sortedItems.length - 1) {
          if (legs.length > 0) routePoint = legs[legs.length - 1].end_location;
        } else {
          // Intermediate item
          if (index - 1 < legs.length) {
            routePoint = legs[index - 1].end_location;
          }
        }

        if (routePoint) {
          // Calculate distance
          const distance =
            google.maps.geometry.spherical.computeDistanceBetween(
              itemLoc,
              routePoint,
            );

          // If distance > 10 meters, draw a line
          if (distance > 10) {
            const line = new google.maps.Polyline({
              path: [itemLoc, routePoint],
              geodesic: true,
              strokeColor: routeColor,
              strokeOpacity: 0.5,
              strokeWeight: 2,
              map: map,
            });
            connectorLinesRef.current.push(line);
          }
        }
      });
    },
    [map, sortedItems, routeColor],
  );

  // Handle directions_changed event - extract new waypoints per segment
  const handleDirectionsChanged = useCallback(() => {
    // Skip if marker is being dragged or we're making programmatic changes
    if (isDraggingMarkerRef.current || isProgrammaticChangeRef.current) {
      return;
    }

    const renderer = rendererRef.current;
    if (!renderer) return;

    const newDirections = renderer.getDirections();
    if (!newDirections) return;

    const legs = newDirections.routes[0]?.legs;
    if (!legs || legs.length === 0) return;

    const currentSortedItems = sortedItemsRef.current;
    const mappings = segmentMappingsRef.current;

    // Each leg corresponds to a segment between items
    // Leg 0 = items[0] -> items[1], Leg 1 = items[1] -> items[2],...
    legs.forEach((leg, legIndex) => {
      if (legIndex >= currentSortedItems.length - 1) return;

      const startItem = currentSortedItems[legIndex];
      const endItem = currentSortedItems[legIndex + 1];
      const segmentKey = getSegmentKey(startItem.id, endItem.id);

      // Extract via_waypoints for this leg
      const viaWaypoints = leg.via_waypoints || [];

      // Get current segment state
      const segmentState = segmentMarkersRef.current.get(segmentKey);
      const currentWaypointCount = segmentState?.currentWaypoints.length ?? 0;

      // Only save if waypoint count changed (new waypoint added)
      if (viaWaypoints.length !== currentWaypointCount) {
        const newWaypoints: UpdateRouteWaypointInput[] = viaWaypoints.map(
          (viaWp, idx) => ({
            lat: viaWp.lat(),
            lng: viaWp.lng(),
            order: idx,
          }),
        );

        // Create temporary RouteWaypoint objects
        const tempWaypoints: RouteWaypoint[] = newWaypoints.map((wp, idx) => ({
          id: `temp-${Date.now()}-${idx}`,
          lat: wp.lat,
          lng: wp.lng,
          order: wp.order,
        }));

        // Clean up old markers for this segment
        if (segmentState) {
          segmentState.markers.forEach((m) => m.setMap(null));
        }

        // Create new markers
        const newMarkers = tempWaypoints
          .map((wp) => createWaypointMarker(wp, segmentKey, startItem, endItem))
          .filter((m): m is google.maps.Marker => m !== null);

        // Update segment state
        segmentMarkersRef.current.set(segmentKey, {
          startItemId: startItem.id,
          endItemId: endItem.id,
          markers: newMarkers,
          currentWaypoints: tempWaypoints,
        });

        // Save to backend
        saveWaypoints(startItem.id, endItem.id, newWaypoints);
      }
    });
  }, [getSegmentKey, createWaypointMarker, saveWaypoints]);

  // Recalculate route using LOCAL state (not props) - used after delete/drag waypoint
  const recalculateWithLocalState = useCallback(() => {
    if (
      !directionsService ||
      !map ||
      !routesLibrary ||
      sortedItems.length < 2
    ) {
      return;
    }

    const firstItem = sortedItems[0];
    const lastItem = sortedItems[sortedItems.length - 1];

    const startCoords = firstItem.place?.location?.coordinates;
    const endCoords = lastItem.place?.location?.coordinates;

    if (!startCoords || !endCoords) return;

    // Build waypoints from LOCAL state (not from props!)
    const { waypoints, mappings } = buildWaypointsFromLocalState();
    segmentMappingsRef.current = mappings;

    const request: google.maps.DirectionsRequest = {
      origin: { lat: startCoords[1], lng: startCoords[0] },
      destination: { lat: endCoords[1], lng: endCoords[0] },
      waypoints: waypoints,
      travelMode: travelMode,
      optimizeWaypoints: false,
    };

    // Set flag to prevent directions_changed from firing during update
    isProgrammaticChangeRef.current = true;

    directionsService.route(request, (result, status) => {
      if (status === google.maps.DirectionsStatus.OK && result) {
        // Clean up existing renderer
        if (rendererRef.current) {
          rendererRef.current.setMap(null);
        }

        // Create single renderer for entire route
        const renderer = new routesLibrary.DirectionsRenderer({
          map,
          directions: result,
          draggable: true,
          suppressMarkers: true,
          preserveViewport: true,
          polylineOptions: {
            strokeColor: routeColor,
            strokeOpacity: 0.8,
            strokeWeight: 5,
            icons: [
              {
                icon: {
                  path: google.maps.SymbolPath.FORWARD_OPEN_ARROW,
                  fillColor: "#ffffff",
                  fillOpacity: 1,
                  scale: 2,
                  strokeColor: routeColor,
                  strokeWeight: 1,
                },
                offset: "0",
                repeat: "100px",
              },
            ],
          },
        });

        rendererRef.current = renderer;

        // Listen for route changes
        renderer.addListener("directions_changed", handleDirectionsChanged);

        // Draw connector lines
        drawConnectorLines(result);

        // Reset flag after a delay
        setTimeout(() => {
          isProgrammaticChangeRef.current = false;
        }, 100);
      } else {
        console.error("Directions request failed:", status);
        isProgrammaticChangeRef.current = false;
      }
    });
  }, [
    directionsService,
    map,
    routesLibrary,
    sortedItems,
    buildWaypointsFromLocalState,
    travelMode,
    handleDirectionsChanged,
    drawConnectorLines,
  ]);

  // Calculate directions with single request
  const calculateDirections = useCallback(() => {
    if (
      !directionsService ||
      !map ||
      !routesLibrary ||
      sortedItems.length < 2
    ) {
      // Clean up if not enough items
      if (rendererRef.current) {
        rendererRef.current.setMap(null);
        rendererRef.current = null;
      }
      segmentMarkersRef.current.forEach((state) => {
        state.markers.forEach((m) => m.setMap(null));
      });
      segmentMarkersRef.current.clear();
      return;
    }

    const firstItem = sortedItems[0];
    const lastItem = sortedItems[sortedItems.length - 1];

    const startCoords = firstItem.place?.location?.coordinates;
    const endCoords = lastItem.place?.location?.coordinates;

    if (!startCoords || !endCoords) return;

    const { waypoints, mappings } = buildWaypointsForRequest();

    // Create cache key from items IDs and waypoints
    const itemIds = sortedItems.map((item) => item.id).join(",");
    const waypointKey = waypoints.map((wp) => `${wp.location}`).join("|");
    const cacheKey = `${itemIds}:${waypointKey}`;

    // Skip if route hasn't changed
    if (cacheKey === lastCalculatedKeyRef.current && rendererRef.current) {
      return;
    }

    lastCalculatedKeyRef.current = cacheKey;
    segmentMappingsRef.current = mappings;

    const request: google.maps.DirectionsRequest = {
      origin: { lat: startCoords[1], lng: startCoords[0] },
      destination: { lat: endCoords[1], lng: endCoords[0] },
      waypoints: waypoints,
      travelMode: travelMode,
      optimizeWaypoints: false, // Keep the order
    };

    directionsService.route(request, (result, status) => {
      if (status === google.maps.DirectionsStatus.OK && result) {
        toast.success("Routes Calculated");
        // Clean up existing renderer
        if (rendererRef.current) {
          rendererRef.current.setMap(null);
        }

        // Create single renderer for entire route
        const renderer = new routesLibrary.DirectionsRenderer({
          map,
          directions: result,
          draggable: true,
          suppressMarkers: true,
          preserveViewport: true,
          polylineOptions: {
            strokeColor: routeColor,
            strokeOpacity: 0.8,
            strokeWeight: 5,
            icons: [
              {
                icon: {
                  path: google.maps.SymbolPath.FORWARD_OPEN_ARROW,
                  fillColor: "#ffffff",
                  fillOpacity: 1,
                  scale: 2,
                  strokeColor: routeColor,
                  strokeWeight: 1,
                },
                offset: "0",
                repeat: "100px",
              },
            ],
          },
        });

        rendererRef.current = renderer;

        // Create markers for all segments
        createAllMarkers();

        // Listen for route changes
        renderer.addListener("directions_changed", handleDirectionsChanged);

        // Draw connector lines
        drawConnectorLines(result);
      } else {
        toast.error("Directions request failed");
        console.error("Directions request failed:", status);
      }
    });
  }, [
    directionsService,
    map,
    routesLibrary,
    sortedItems,
    buildWaypointsForRequest,
    travelMode,
    createAllMarkers,
    handleDirectionsChanged,
    drawConnectorLines,
  ]);

  // Effect to calculate directions when dependencies change
  useEffect(() => {
    calculateDirections();
  }, [calculateDirections]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rendererRef.current) {
        rendererRef.current.setMap(null);
        rendererRef.current = null;
      }
      segmentMarkersRef.current.forEach((state) => {
        state.markers.forEach((m) => m.setMap(null));
      });
      segmentMarkersRef.current.clear();

      connectorLinesRef.current.forEach((line) => line.setMap(null));
      connectorLinesRef.current = [];
    };
  }, []);

  return null;
}

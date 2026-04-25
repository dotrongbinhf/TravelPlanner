import React from "react";
import { UtensilsCrossed, Star, ExternalLink, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlaceCarouselWidget } from "./PlaceCarouselWidget";
import { useItineraryContext } from "@/contexts/ItineraryContext";

export interface RestaurantWidgetProps {
  data: any;
}

export function RestaurantWidget({ data }: RestaurantWidgetProps) {
  if (!data?.meals || data.meals.length === 0) {
    return null;
  }

  const { setFocusLocation, clearPlaceSelection, setSelectedChatPlace } = useItineraryContext();

  // Extract lat/lng from db_data (GeoJSON: [lng, lat])
  const _focusOnMap = (item: any) => {
    const coords = item.db_data?.location?.coordinates;
    const location = coords && coords.length === 2 
      ? { lat: coords[1], lng: coords[0] }
      : (item._location?.lat && item._location?.lng ? { lat: item._location.lat, lng: item._location.lng } : null);

    if (location) {
      setFocusLocation(location);
      setSelectedChatPlace({
        id: item.id || item.name || item.recommend_restaurant_name,
        placeId: item.place_id || item.placeId,
        name: item.name || item.recommend_restaurant_name,
        location,
        source: "restaurant"
      });
    }
  };

  const handleOpenMap = (placeName: string, placeId?: string) => {
    let url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(placeName)}`;
    if (placeId) {
      url += `&query_place_id=${placeId}`;
    }
    window.open(url, "_blank");
  };

  const getImage = (item: any) =>
    item.db_data?.imageUrl ||
    item.db_data?.thumbnail ||
    "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&q=80";

  // Build a flat list of all restaurants (recommended + alternatives) across all meals
  const allRestaurants: any[] = [];
  const recommendedNames = new Set<string>();

  data.meals.forEach((meal: any, mIdx: number) => {
    if (meal.name) {
      recommendedNames.add(meal.name);
      allRestaurants.push({
        ...meal,
        id: `meal-${mIdx}-${meal.name}`,
        _isRecommended: true,
        _mealLabel:
          meal.day > 0 && meal.meal_type !== "standalone"
            ? `Day ${meal.day} · ${meal.meal_type}`
            : "",
      });
    }
    (meal.alternatives || []).forEach((alt: any, aIdx: number) => {
      if (typeof alt === "string") {
        allRestaurants.push({
          id: `alt-${mIdx}-${aIdx}`,
          name: alt,
          _isRecommended: false,
          _mealLabel:
            meal.day > 0 && meal.meal_type !== "standalone"
              ? `Day ${meal.day} · ${meal.meal_type}`
              : "",
        });
      } else {
        allRestaurants.push({
          ...alt,
          id: alt.place_id || alt.name || `alt-${mIdx}-${aIdx}`,
          _isRecommended: false,
          _mealLabel:
            meal.day > 0 && meal.meal_type !== "standalone"
              ? `Day ${meal.day} · ${meal.meal_type}`
              : "",
        });
      }
    });
  });

  if (allRestaurants.length === 0) return null;

  return (
    <PlaceCarouselWidget
      title="Recommended Dining"
      subtitle="Curated Local Places"
      theme="orange"
      headerIcon={
        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center border border-orange-100 shadow-sm">
          <UtensilsCrossed className="w-4 h-4 text-orange-500" />
        </div>
      }
      items={allRestaurants}
      renderCard={(rest: any, index: number, onClick: () => void) => (
        <div
          key={rest.id}
          onClick={() => {
            onClick();
            _focusOnMap(rest);
          }}
          className="relative flex-[0_0_160px] sm:flex-[0_0_180px] md:flex-[0_0_200px] cursor-pointer group rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300 border border-slate-200/50"
        >
          <div className="relative h-[240px] w-full bg-slate-100">
            <img
              src={getImage(rest)}
              alt={rest.name}
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&q=80";
              }}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

            {/* Top Badge */}
            {rest._isRecommended && (
              <div className="absolute top-2 left-2 rounded-lg px-2 py-1.5 text-xs bg-orange-50 text-orange-900 font-bold">
                Recommended
              </div>
            )}

            {/* Bottom Overlay Info */}
            <div className="absolute bottom-3 left-3 right-3 flex flex-col gap-1 text-white">
              <h4 className="font-bold text-[13px] leading-tight line-clamp-2 drop-shadow-md">
                {rest.name}
              </h4>

              <div className="flex items-center gap-1.5 text-[11px] font-medium drop-shadow-sm opacity-90">
                {(rest.rating || rest.db_data?.reviewRating) && (
                  <>
                    <Star className="w-3 h-3 fill-white text-white" />
                    <span>
                      {(rest.rating || rest.db_data?.reviewRating)?.toFixed?.(1) || rest.rating || "-"}
                    </span>
                  </>
                )}
                {rest._mealLabel && (
                  <span className="opacity-80">· {rest._mealLabel}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      onDetailClose={() => clearPlaceSelection()}
      renderDetail={(selected: any) => (
        <>
          <div className="w-full sm:w-3/5 md:w-[60%] relative h-64 sm:h-auto min-h-[300px] shrink-0">
            <img
              src={getImage(selected)}
              alt={selected.name}
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&q=80";
              }}
              className="absolute inset-0 w-full h-full object-cover"
            />
            {selected._isRecommended && (
              <div className="absolute top-3 left-3 bg-orange-500/90 backdrop-blur-sm text-white px-2.5 py-1 rounded-md shadow-sm text-[10px] font-bold uppercase tracking-widest z-10">
                Recommended
              </div>
            )}
          </div>

          <div className="flex-1 p-5 flex flex-col relative bg-white pt-10 sm:pt-5">
            <h4 className="font-bold text-slate-900 text-lg leading-tight mt-1 mb-2 pr-4">
              {selected.name}
            </h4>

            {/* Rating + Price Level */}
            <div className="flex items-center gap-2 mb-3">
              {(selected.rating || selected.db_data?.reviewRating) && (
                <div className="flex items-center gap-1">
                  <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                  <span className="text-sm font-bold text-slate-800">
                    {(selected.rating || selected.db_data?.reviewRating)?.toFixed(1)}
                  </span>
                </div>
              )}
              {(selected.user_ratings_total || selected.db_data?.reviewCount) > 0 && (
                <span className="text-sm text-slate-500">
                  ({(selected.user_ratings_total || selected.db_data?.reviewCount)?.toLocaleString()})
                </span>
              )}
              {selected.price_level > 0 && (
                <span className="text-emerald-600 font-bold text-sm tracking-widest">
                  {"$".repeat(selected.price_level)}
                </span>
              )}
            </div>

            {/* Category */}
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">
              {selected.db_data?.category || "Restaurant"}
            </div>

            {/* Address */}
            {selected.db_data?.address && (
              <div className="flex items-start gap-1.5 text-slate-500 mb-4">
                <MapPin className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span className="text-[12px] font-medium leading-relaxed">
                  {selected.db_data.address}
                </span>
              </div>
            )}

            {/* Note / Why here */}
            {(selected.note || selected.justification) && (
              <div className="mb-4 pt-3 border-t border-slate-100">
                <p className="text-[13px] text-slate-600 leading-relaxed">
                  <span className="text-orange-500 font-bold mr-1.5">
                    Why here?
                  </span>
                  {selected.note || selected.justification}
                </p>
              </div>
            )}

            <div className="mt-auto flex flex-col gap-4">
              {/* Meal label */}
              {selected._mealLabel && (
                <div className="flex justify-between items-end">
                  <span className="text-sm font-bold text-slate-800 capitalize">
                    {selected._mealLabel}
                  </span>
                  {selected.estimated_cost_total > 0 && (
                    <span className="text-xl font-black text-slate-900">
                      {new Intl.NumberFormat("vi-VN").format(selected.estimated_cost_total)} VND
                    </span>
                  )}
                </div>
              )}

              <Button
                className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium h-11 rounded-xl"
                onClick={() => handleOpenMap(selected.name, selected.place_id)}
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                View on Google Maps
              </Button>
            </div>
          </div>
        </>
      )}
    />
  );
}

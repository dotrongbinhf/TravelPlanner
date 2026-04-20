import React from "react";
import { Map, Star, ExternalLink, ArrowRight } from "lucide-react";
import { PlaceCarouselWidget } from "./PlaceCarouselWidget";
import { useItineraryContext } from "@/contexts/ItineraryContext";

export interface AttractionWidgetProps {
  data: any;
}

export function AttractionWidget({ data }: AttractionWidgetProps) {
  if (!data?.segments || data.segments.length === 0) {
    return null;
  }

  const { selectPlaceFromMap, clearPlaceSelection } = useItineraryContext();

  // Flatten all attractions across segments
  const allAttractions = data.segments.flatMap((s: any) =>
    (s.attractions || []).map((a: any, idx: number) => ({
      ...a,
      id: a.place_id || a.name || `attr-${idx}`,
      _segment: s.segment_name,
    }))
  );
  if (allAttractions.length === 0) return null;

  const handleOpenMap = (placeName: string, placeId?: string) => {
    let url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(placeName)}`;
    if (placeId) {
      url += `&query_place_id=${placeId}`;
    }
    window.open(url, "_blank");
  };

  const getImage = (attr: any) =>
    attr.db_data?.imageUrl ||
    attr.db_data?.thumbnail ||
    "https://images.unsplash.com/photo-1499696010180-025ef6e1a8f9?w=800&q=80";

  return (
    <PlaceCarouselWidget
      title="Recommended Places"
      subtitle="Top Sights & Attractions"
      theme="rose"
      headerIcon={
        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center border border-rose-100 shadow-sm">
          <Map className="w-4 h-4 text-rose-500" />
        </div>
      }
      items={allAttractions}
      renderCard={(attr: any, index: number, onClick: () => void) => {
        const rating = attr.db_data?.reviewRating || attr.rating;
        const reviews = attr.db_data?.reviewCount || attr.user_ratings_total;

        return (
          <div
            key={attr.id}
            onClick={() => {
              onClick();
              if (attr.place_id || attr.db_data?.placeId) {
                selectPlaceFromMap(attr.place_id || attr.db_data?.placeId);
              }
            }}
            className="relative flex-[0_0_160px] sm:flex-[0_0_180px] md:flex-[0_0_200px] cursor-pointer group rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300 border border-slate-200/50"
          >
            <div className="relative h-[240px] w-full bg-slate-100">
              <img
                src={getImage(attr)}
                alt={attr.name}
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    "https://images.unsplash.com/photo-1499696010180-025ef6e1a8f9?w=800&q=80";
                }}
                className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

              {/* Must Visit Badge */}
              {attr.must_visit && (
                <div className="absolute top-2 left-2 rounded-lg px-2 py-1.5 text-xs bg-rose-50 text-rose-900 font-bold">
                  Must Visit
                </div>
              )}

              {/* Bottom Overlay Info */}
              <div className="absolute bottom-3 left-3 right-3 flex flex-col gap-1 text-white">
                <h4 className="font-bold text-[13px] leading-tight line-clamp-2 drop-shadow-md">
                  {attr.name}
                </h4>

                <div className="flex items-center gap-1.5 text-[11px] font-medium drop-shadow-sm opacity-90">
                  {rating ? (
                    <>
                      <Star className="w-3 h-3 fill-white text-white" />
                      <span>{rating.toFixed?.(1) || rating}</span>
                      {reviews > 0 && <span className="opacity-80">· {reviews}</span>}
                    </>
                  ) : (
                    <span>No rating</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      }}
      onDetailClose={() => clearPlaceSelection()}
      renderDetail={(selected: any) => (
        <>
          <div className="w-full sm:w-3/5 md:w-[60%] relative h-64 sm:h-auto min-h-[300px] shrink-0">
            <img
              src={getImage(selected)}
              alt={selected.name}
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  "https://images.unsplash.com/photo-1499696010180-025ef6e1a8f9?w=800&q=80";
              }}
              className="absolute inset-0 w-full h-full object-cover"
            />
            {selected.must_visit && (
              <div className="absolute top-3 left-3 bg-rose-500/90 backdrop-blur-sm text-white px-2.5 py-1 rounded-md shadow-sm text-[10px] font-bold uppercase tracking-widest z-10">
                Must Visit
              </div>
            )}
          </div>

          <div className="flex-1 p-5 flex flex-col relative bg-white pt-10 sm:pt-5">
            <h4 className="font-bold text-slate-900 text-lg leading-tight mt-1 mb-2 pr-4">
              {selected.name}
            </h4>

            {/* Category */}
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-4">
              {selected.db_data?.category || selected._segment || "Attraction"}
            </div>

            {/* Notes — the engaging overview */}
            {selected.notes && (
              <p className="text-[13px] text-slate-600 leading-relaxed mb-4">
                {selected.notes}
              </p>
            )}

            {/* Includes */}
            {selected.includes && selected.includes.length > 0 && (
              <div className="mb-4 pt-3 border-t border-slate-100">
                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block mb-2">
                  Includes
                </span>
                <div className="flex flex-wrap gap-2">
                  {selected.includes.map((inc: any, iIdx: number) => (
                    <span
                      key={iIdx}
                      className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-[11px] font-semibold px-2 py-1 rounded-md"
                    >
                      <ArrowRight className="w-3 h-3 text-slate-400" />
                      {inc.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-auto flex flex-col gap-4">
              {/* Entrance fee */}
              {selected.estimated_entrance_fee && (
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-end">
                    <span className="text-sm font-bold text-slate-800">
                      Entrance
                    </span>
                    <span className="text-xl font-black text-slate-900">
                      {selected.estimated_entrance_fee.total === 0
                        ? "Free"
                        : `${new Intl.NumberFormat("vi-VN").format(selected.estimated_entrance_fee.total)} VND`}
                    </span>
                  </div>
                  {selected.estimated_entrance_fee.total > 0 && selected.estimated_entrance_fee.note && (
                    <span className="text-[11px] font-medium text-slate-400 text-right">
                      {selected.estimated_entrance_fee.note}
                    </span>
                  )}
                </div>
              )}

              <Button
                className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium h-11 rounded-xl"
                onClick={() => handleOpenMap(selected.name, selected.placeId)}
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

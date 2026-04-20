import React from "react";
import { Star, ExternalLink, MapPin } from "lucide-react";
import { PlaceCarouselWidget } from "./PlaceCarouselWidget";
import { useItineraryContext } from "@/contexts/ItineraryContext";

export interface HotelWidgetProps {
  data: any;
}

export function HotelWidget({ data }: HotelWidgetProps) {
  if (!data?.segments || data.segments.length === 0) {
    return (
      <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 flex items-center justify-center gap-3 animate-pulse my-4 shadow-sm">
        <div className="w-5 h-5 rounded-full border-[3px] border-blue-500 border-t-transparent animate-spin" />
        <span className="text-[15px] font-semibold text-slate-600 tracking-tight">
          Finding the best stays...
        </span>
      </div>
    );
  }

  const { selectPlaceFromMap, clearPlaceSelection } = useItineraryContext();

  const segment = data.segments[0];

  const recommendedHotel = {
    id: segment.recommend_hotel_name, // Unique key
    name: segment.recommend_hotel_name,
    thumbnail: segment.thumbnail,
    link: segment.link,
    totalRate: segment.totalRate || "Price upon request",
    hotel_class: segment.hotel_class || "",
    overallRating: segment.overallRating,
    reviews: segment.reviews,
    checkInTime: segment.checkInTime,
    checkOutTime: segment.checkOutTime,
    _isRecommended: true,
  };

  const allHotels = [
    recommendedHotel,
    ...(segment.alternatives || []).map((alt: any, idx: number) => ({
      ...alt,
      id: alt.name || `alt-${idx}`,
      _isRecommended: false,
    })),
  ];

  if (!allHotels || allHotels.length === 0) return null;

  return (
    <PlaceCarouselWidget
      title="SerpAPI - Google Hotels"
      subtitle="Recommended for you"
      theme="sky"
      headerIcon={
        <img
          src="/images/plans/serpapi.png"
          alt="SerpApi"
          className="w-full h-full object-cover"
        />
      }
      items={allHotels}
      renderCard={(hotel: any, index: number, onClick: () => void) => (
        <div
          key={hotel.id}
          onClick={() => {
            onClick();
            if (hotel.place_id || hotel.db_data?.placeId) {
              selectPlaceFromMap(hotel.place_id || hotel.db_data?.placeId);
            }
          }}
          className="relative flex-[0_0_160px] sm:flex-[0_0_180px] md:flex-[0_0_200px] cursor-pointer group rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300 border border-slate-200/50"
        >
          <div className="relative h-[240px] w-full bg-slate-100">
            <img
              src={
                hotel.thumbnail ||
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80"
              }
              alt={hotel.name}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

            {hotel._isRecommended && (
              <div className="absolute top-2 left-2 rounded-lg px-2 py-1.5 text-xs bg-sky-50 text-sky-900 font-bold">
                Recommended
              </div>
            )}

            <div className="absolute bottom-3 left-3 right-3 flex flex-col gap-1 text-white">
              <h4 className="font-bold text-[13px] leading-tight line-clamp-2 drop-shadow-md">
                {hotel.name}
              </h4>

              <div className="flex items-center gap-1.5 text-[11px] font-medium drop-shadow-sm opacity-90">
                <Star className="w-3 h-3 fill-white text-white" />
                <span>{hotel.overallRating !== "N/A" ? hotel.overallRating : "-"}</span>
                {hotel.reviews > 0 && (
                  <span className="opacity-80">· {hotel.reviews}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      onDetailClose={() => clearPlaceSelection()}
      renderDetail={(selectedHotel: any) => (
        <>
          <div className="w-full sm:w-3/5 md:w-[60%] relative h-64 sm:h-auto min-h-[300px] shrink-0">
            <img
              src={
                selectedHotel.thumbnail ||
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80"
              }
              alt={selectedHotel.name}
              className="absolute inset-0 w-full h-full object-cover"
            />
          </div>

          <div className="flex-1 p-5 flex flex-col relative bg-white pt-10 sm:pt-5">
            <h4 className="font-bold text-slate-900 text-lg leading-tight mt-1 mb-3 pr-4">
              {selectedHotel.name}
            </h4>

            <div className="flex items-center gap-2 mb-6">
              <Star className="w-4 h-4 fill-slate-800 text-slate-800" />
              <span className="text-sm font-bold text-slate-800">
                {selectedHotel.overallRating !== "N/A" ? selectedHotel.overallRating : "N/A"}
              </span>
              {selectedHotel.reviews > 0 && (
                <span className="text-sm text-slate-500">
                  ({selectedHotel.reviews})
                </span>
              )}
            </div>

            <div className="flex flex-col gap-3 text-sm text-slate-600 mb-6">
              <div className="flex justify-between items-center border-b border-slate-100 pb-2">
                <span className="text-slate-500">Check-in</span>
                <span className="font-medium text-slate-800">
                  {selectedHotel.checkInTime !== "N/A" ? selectedHotel.checkInTime : "--"}
                </span>
              </div>
              <div className="flex justify-between items-center border-b border-slate-100 pb-2">
                <span className="text-slate-500">Check-out</span>
                <span className="font-medium text-slate-800">
                  {selectedHotel.checkOutTime !== "N/A" ? selectedHotel.checkOutTime : "--"}
                </span>
              </div>
            </div>

            <div className="mt-auto flex flex-col gap-4">
              <div className="flex justify-between items-end">
                <span className="text-sm font-bold text-slate-800">Total Price</span>
                <span className="text-xl font-black text-slate-900">
                  {selectedHotel.totalRate !== "N/A" ? selectedHotel.totalRate : "N/A"}
                </span>
              </div>

              <Button
                className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium h-11 rounded-xl"
                asChild
                disabled={!selectedHotel.link}
              >
                <a href={selectedHotel.link || "#"} target="_blank" rel="noopener noreferrer">
                  Book
                </a>
              </Button>
            </div>
          </div>
        </>
      )}
    />
  );
}

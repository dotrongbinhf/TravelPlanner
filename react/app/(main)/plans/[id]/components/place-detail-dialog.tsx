import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CustomDialog } from "@/components/custom-dialog";
import {
  DatePickerInput,
  DateTimePickerType,
  TimePicker,
  TimePickerType,
} from "@/components/time-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Plan } from "@/types/plan";
import {
  Clock,
  MapPin,
  Plus,
  Star,
  X,
  Globe,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Maximize2,
} from "lucide-react";
import { format, addHours, setHours, setMinutes } from "date-fns";
import { Place } from "@/types/place";
import { getPlaceByPlaceId } from "@/api/place/place";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

import { createItineraryItem } from "@/api/itineraryItem/itineraryItem";
import { ItineraryItem } from "@/types/itineraryItem";
import { AxiosError } from "axios";
import toast from "react-hot-toast";
import ItineraryItemEditor from "./sections/itinerary-item-editor";

interface PlaceDetailDialogProps {
  placeId: string;
  onClose: () => void;
  plan: Plan | null;
  onAddItem: (item: ItineraryItem) => void;
}

export default function PlaceDetailDialog({
  placeId,
  onClose,
  plan,
  onAddItem,
}: PlaceDetailDialogProps) {
  const [place, setPlace] = useState<Place | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [selectedDayId, setSelectedDayId] = useState<string>("");
  const [startTime, setStartTime] = useState<Date | undefined>();
  const [endTime, setEndTime] = useState<Date | undefined>();
  const [isOpenDialog, setIsOpenDialog] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  const getSelectedDate = () => {
    if (!plan || !plan.itineraryDays || !selectedDayId) return undefined;
    const day = plan.itineraryDays.find((d) => d.id === selectedDayId);
    if (!day) return undefined;
    const date = new Date(plan.startTime);
    date.setDate(date.getDate() + day.order);
    date.setHours(0, 0, 0, 0);
    return date;
  };

  useEffect(() => {
    const baseDate = getSelectedDate();
    if (baseDate) {
      if (startTime) {
        const newStart = new Date(baseDate);
        newStart.setHours(startTime.getHours(), startTime.getMinutes());
        if (newStart.getTime() !== startTime.getTime()) setStartTime(newStart);
      }
      if (endTime) {
        const newEnd = new Date(baseDate);
        newEnd.setHours(endTime.getHours(), endTime.getMinutes());
        if (newEnd.getTime() !== endTime.getTime()) setEndTime(newEnd);
      }
    }
  }, [selectedDayId, plan]);

  const handleAddToItinerary = async () => {
    if (!place || !selectedDayId || !startTime || !endTime) return;

    setAdding(true);
    try {
      const response = await createItineraryItem(selectedDayId, {
        placeId: place.placeId,
        startTime: format(startTime, "HH:mm"),
        endTime: format(endTime, "HH:mm"),
      });

      onAddItem(response);
      toast.success("Added to itinerary successfully");
      setIsOpenDialog(false);
      onClose();
    } catch (error) {
      console.error("Failed to add to itinerary:", error);
      if (error instanceof AxiosError) {
        toast.error(
          error.response?.data?.message ?? "Failed to add to itinerary",
        );
      } else {
        toast.error("Failed to add to itinerary");
      }
    } finally {
      setAdding(false);
    }
  };

  useEffect(() => {
    if (!placeId) return;

    const fetchPlace = async () => {
      setLoading(true);
      try {
        const data = await getPlaceByPlaceId(placeId);
        setPlace(data);
      } catch (error) {
        console.error("Failed to fetch place details:", error);
        setPlace(null);
      } finally {
        setLoading(false);
      }
    };

    fetchPlace();
  }, [placeId]);

  // Calculate rating distribution
  const totalReviews = place?.reviewCount || 0;
  const getPercentage = (count: number) => {
    if (totalReviews === 0) return 0;
    return (count / totalReviews) * 100;
  };

  const allPhotos = [
    ...(place?.images?.map((img) => img.image) || []),
    // ...(place?.userReviews?.flatMap((r) => r.images) || []),
  ];

  return (
    <div className="absolute bottom-2 left-2 right-2 z-10 flex flex-col items-center pointer-events-none">
      <Card className="p-0 w-full h-[45vh] md:h-[40vh] bg-white pointer-events-auto shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-300 border-0 ring-1 ring-gray-200">
        <div className="h-full flex flex-col md:flex-row relative">
          {/* <Button
            variant="ghost"
            size="icon"
            className="absolute top-2 right-2 z-20 bg-white/50 backdrop-blur-md hover:bg-white/80 rounded-full h-8 w-8 text-gray-700"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button> */}

          {loading ? (
            <div className="w-full h-full flex items-center justify-center flex-col space-y-4">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
              <p className="text-sm text-gray-500 font-medium">
                Loading details...
              </p>
            </div>
          ) : place ? (
            <>
              {/* LEFT SIDE: Image & Key Info (35% width on desktop) */}
              <div className="w-full md:w-[35%] h-[200px] md:h-full relative shrink-0 group">
                <img
                  src={place.thumbnail}
                  alt={place.title}
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

                {/* Info Overlay */}
                <div className="absolute bottom-4 left-4 right-4 text-white">
                  <h2 className="text-xl font-bold leading-tight mb-2 drop-shadow-md line-clamp-2">
                    {place.title}
                  </h2>
                  <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-white/90">
                    <div className="flex items-center gap-1 bg-yellow-500 text-yellow-950 px-2 py-0.5 rounded-full text-xs font-bold shadow-sm">
                      {place.reviewRating.toFixed(1)}{" "}
                      <Star className="w-3 h-3 fill-yellow-950" />
                    </div>
                    <span className="text-xs text-gray-200">
                      ({place.reviewCount} reviews)
                    </span>
                    <span className="hidden md:inline text-gray-400">•</span>
                    <span className="bg-white/20 backdrop-blur-sm px-2 py-0.5 rounded-md border border-white/20 text-xs">
                      {place.category}
                    </span>
                  </div>
                </div>
              </div>

              {/* RIGHT SIDE: Details & Tabs (65% width on desktop) */}
              <div className="flex-1 flex flex-col h-full bg-white min-w-0">
                <Tabs
                  value={activeTab}
                  onValueChange={setActiveTab}
                  className="flex-1 flex flex-col min-h-0"
                >
                  <TabsList className="w-full justify-between h-10 bg-transparent p-0 px-2">
                    {["overview", "photos", "reviews"].map((tab) => (
                      <TabsTrigger
                        key={tab}
                        value={tab}
                        className="relative px-1 pb-2 font-semibold text-gray-500 transition-colors hover:text-blue-600
                          after:content-['']
                          after:absolute
                          after:left-1/2
                          after:-bottom-[1px]
                          after:h-[2px]
                          after:w-0
                          after:-translate-x-1/2
                          after:bg-blue-600
                          after:transition-all
                          after:duration-300
                          data-[state=active]:after:w-2/3
                          data-[state=active]:text-blue-600
                          data-[state=active]:shadow-none"
                      >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  <div className="flex-1 overflow-y-auto p-3 custom-scrollbar">
                    <TabsContent value="overview" className="mt-0 space-y-5">
                      {/* Description */}
                      {place.description && (
                        <div className="text-sm text-gray-600 leading-relaxed">
                          {place.description}
                        </div>
                      )}

                      {/* Info Grid */}
                      <div className="grid grid-cols-1 gap-3">
                        <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                          <MapPin className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
                          <div className="space-y-0.5">
                            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                              Address
                            </span>
                            <p className="text-sm text-gray-900 font-medium leading-tight">
                              {place.address}
                            </p>
                          </div>
                        </div>

                        {place.openHours && (
                          <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                            <Clock className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
                            <div className="space-y-1 w-full">
                              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                                Opening Hours
                              </span>
                              <div className="space-y-1 text-sm">
                                {Object.entries(place.openHours).map(
                                  ([day, hours]) => (
                                    <div
                                      key={day}
                                      className="flex justify-between border-b border-gray-100 last:border-0 pb-1 last:pb-0"
                                    >
                                      <span className="capitalize text-gray-600 w-24">
                                        {day}
                                      </span>
                                      <span className="font-medium text-gray-900 text-right flex-1">
                                        {hours && hours.length > 0 ? (
                                          hours.join(", ")
                                        ) : (
                                          <span className="text-red-500">
                                            Closed
                                          </span>
                                        )}
                                      </span>
                                    </div>
                                  ),
                                )}
                              </div>
                            </div>
                          </div>
                        )}

                        {(place.website || place.link) && (
                          <div className="flex flex-wrap gap-2">
                            {place.website && (
                              <a
                                href={place.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-100 transition-colors"
                              >
                                <Globe className="w-4 h-4" /> Website
                              </a>
                            )}
                            {place.link && (
                              <a
                                href={place.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
                              >
                                <ExternalLink className="w-4 h-4" /> Maps
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    </TabsContent>

                    <TabsContent value="photos" className="mt-0">
                      {allPhotos.length > 0 ? (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                          {allPhotos.map((photo, i) => (
                            <div
                              key={i}
                              className="aspect-square rounded-md overflow-hidden bg-gray-100 relative group"
                            >
                              <img
                                src={photo}
                                alt={`Place photo ${i}`}
                                className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                                loading="lazy"
                              />
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                          <Maximize2 className="w-8 h-8 opacity-20 mb-2" />
                          <p className="text-sm">No photos available</p>
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="reviews" className="mt-0 space-y-6">
                      {/* Summary */}
                      <div className="flex items-center gap-6 bg-gray-50 p-4 rounded-xl">
                        <div className="text-center">
                          <div className="text-4xl font-bold text-gray-900">
                            {place.reviewRating.toFixed(1)}
                          </div>
                          <div className="flex gap-0.5 justify-center my-1">
                            {[...Array(5)].map((_, i) => (
                              <Star
                                key={i}
                                className={cn(
                                  "w-3 h-3",
                                  i < Math.round(place.reviewRating)
                                    ? "fill-yellow-400 text-yellow-400"
                                    : "text-gray-300",
                                )}
                              />
                            ))}
                          </div>
                          <div className="text-xs text-gray-500 font-medium">
                            {place.reviewCount} reviews
                          </div>
                        </div>
                        <div className="flex-1 space-y-1">
                          {["5", "4", "3", "2", "1"].map((rating) => {
                            const pct = getPercentage(
                              place.reviewsPerRating?.[rating] || 0,
                            );
                            return (
                              <div
                                key={rating}
                                className="flex items-center gap-2 text-xs"
                              >
                                <span className="w-3 text-gray-500 font-medium">
                                  {rating}
                                </span>
                                <Progress value={pct} className="h-1.5" />
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Review List */}
                      <div className="space-y-4">
                        {place.userReviews?.length > 0 ? (
                          place.userReviews.map((review, i) => (
                            <div
                              key={i}
                              className="border-b border-gray-100 last:border-0 pb-4 last:pb-0"
                            >
                              <div className="flex justify-between items-start mb-2">
                                <div className="flex items-center gap-3">
                                  <div className="w-9 h-9 rounded-full bg-gray-200 overflow-hidden shrink-0 ring-2 ring-white shadow-sm">
                                    <img
                                      src={review.profilePicture}
                                      alt={review.name}
                                      className="w-full h-full object-cover"
                                    />
                                  </div>
                                  <div>
                                    <h4 className="text-sm font-semibold text-gray-900">
                                      {review.name}
                                    </h4>
                                    <span className="text-xs text-gray-500">
                                      {review.when}
                                    </span>
                                  </div>
                                </div>
                                <div className="flex items-center gap-1 bg-yellow-50 px-2 py-1 rounded text-xs font-bold text-yellow-700">
                                  {review.rating}{" "}
                                  <Star className="w-3 h-3 fill-yellow-500" />
                                </div>
                              </div>
                              <p className="text-sm text-gray-600 leading-relaxed">
                                {review.description}
                              </p>
                              {review.images && review.images.length > 0 && (
                                <div className="flex gap-2 mt-3 overflow-x-auto pb-2">
                                  {review.images.map((img, idx) => (
                                    <img
                                      key={idx}
                                      src={img}
                                      alt="Review"
                                      className="w-16 h-16 object-cover rounded-md border border-gray-100"
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          ))
                        ) : (
                          <p className="text-center text-sm text-gray-500 py-6">
                            No reviews yet.
                          </p>
                        )}
                      </div>
                    </TabsContent>
                  </div>

                  {/* Footer Action */}
                  <div className="p-3 flex justify-end gap-3 shrink-0">
                    <Button variant="outline" onClick={onClose}>
                      Close
                    </Button>
                    <Button
                      onClick={() => setIsOpenDialog(true)}
                      className="bg-primary hover:bg-primary/90 text-white shadow-lg shadow-primary/20"
                    >
                      <Plus className="w-4 h-4 mr-2" /> Add to Itinerary
                    </Button>

                    {plan?.startTime && plan?.itineraryDays && (
                      <CustomDialog
                        open={isOpenDialog}
                        onOpenChange={setIsOpenDialog}
                        title="Add Place to Itinerary"
                        description={`Choose a day and time to add "${place.title}" to your trip.`}
                        confirmLabel={adding ? "Adding..." : "Add Place"}
                        isDisabled={
                          !selectedDayId || !startTime || !endTime || adding
                        }
                        onConfirm={handleAddToItinerary}
                      >
                        <ItineraryItemEditor
                          selectedDayId={selectedDayId}
                          setSelectedDayId={setSelectedDayId}
                          itineraryDays={plan?.itineraryDays}
                          planStartTime={plan?.startTime}
                          startTime={startTime}
                          endTime={endTime}
                          setStartTime={setStartTime}
                          setEndTime={setEndTime}
                        />
                      </CustomDialog>
                    )}
                  </div>
                </Tabs>
              </div>
            </>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center space-y-2">
              <MapPin className="w-12 h-12 text-gray-300" />
              <p className="text-gray-900 font-medium">
                Place Details Unavailable
              </p>
              <Button variant="outline" onClick={onClose} className="mt-4">
                Close Info
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

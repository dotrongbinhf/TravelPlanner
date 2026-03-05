import { Coffee, Footprints, Zap, LucideIcon } from "lucide-react";

export const INTEREST_OPTIONS = [
  "History & Culture",
  "Food & Cuisine",
  "Nature & Outdoors",
  "Adventure & Sports",
  "Shopping",
  "Nightlife",
  "Photography",
  "Architecture",
  "Art & Museums",
  "Beach & Relaxation",
  "Local Experiences",
  "Spiritual & Wellness",
];

export const PACE_OPTIONS: {
  value: string;
  label: string;
  desc: string;
  icon: LucideIcon;
  iconClass: string;
}[] = [
  {
    value: "relaxed",
    label: "Relaxed",
    desc: "2-3 places/day",
    icon: Coffee,
    iconClass: "text-emerald-500",
  },
  {
    value: "moderate",
    label: "Moderate",
    desc: "4-5 places/day",
    icon: Footprints,
    iconClass: "text-blue-500",
  },
  {
    value: "packed",
    label: "Packed",
    desc: "6+ places/day",
    icon: Zap,
    iconClass: "text-orange-500",
  },
];

export const BUDGET_OPTIONS = [
  {
    value: "budget",
    label: "Budget",
    desc: "Hostels, street food",
    icon: "💰",
  },
  {
    value: "moderate",
    label: "Mid-range",
    desc: "Hotels, restaurants",
    icon: "💳",
  },
  {
    value: "luxury",
    label: "Luxury",
    desc: "5-star, fine dining",
    icon: "💎",
  },
];

export const TRAVEL_TRANSPORT_OPTIONS = [
  { value: "airplane", label: "Airplane" },
  { value: "train", label: "Train" },
  { value: "coach", label: "Coach" },
  { value: "car", label: "Car" },
  { value: "motorbike", label: "Motorbike" },
  { value: "any", label: "Any" },
  { value: "other", label: "Other..." },
];

export const LOCAL_TRANSPORT_OPTIONS = [
  { value: "same_as_travel", label: "Same as travel transport" },
  { value: "walking", label: "Walking" },
  { value: "public_transit", label: "Public transit" },
  { value: "car_own", label: "Car" },
  { value: "motorbike_own", label: "Motorbike" },
  { value: "taxi", label: "Taxi / Ride-share" },
  { value: "any", label: "Any" },
  { value: "other", label: "Other..." },
];

export const HOTEL_STAR_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "3", label: "3 ⭐" },
  { value: "4", label: "4 ⭐" },
  { value: "5", label: "5 ⭐" },
];

export const HOTEL_ROOM_OPTIONS = [
  { value: "any", label: "Any type" },
  { value: "single", label: "Single" },
  { value: "double", label: "Double" },
  { value: "twin", label: "Twin" },
  { value: "suite", label: "Suite" },
  { value: "family", label: "Family" },
];

export const HOTEL_AMENITY_OPTIONS = [
  "Free WiFi",
  "Breakfast included",
  "Pool",
  "Gym",
  "Parking",
  "Airport shuttle",
  "Pet-friendly",
  "Kitchen",
];

export const FLIGHT_CABIN_OPTIONS = [
  { value: "any", label: "Any class" },
  { value: "economy", label: "Economy" },
  { value: "premium_economy", label: "Premium Economy" },
  { value: "business", label: "Business" },
  { value: "first", label: "First Class" },
];

export const FLIGHT_STOP_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "nonstop", label: "Nonstop" },
  { value: "1_stop", label: "1 stop max" },
  { value: "2_stops", label: "2 stops max" },
];

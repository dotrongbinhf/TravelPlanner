export interface PromptBuilderData {
  origin: string;
  destination: string;
  travelTransport: string;
  customTravelTransport: string;
  localTransport: string;
  customLocalTransport: string;
  startDate: Date | null;
  endDate: Date | null;
  adults: number;
  children: number;
  infants: number;
  interests: string[];
  pace: string;
  budgetLevel: string;
  additionalRequests: string;
  needHotel: boolean;
  needFlight: boolean;
  hotelPreferences: HotelPreferences;
  flightPreferences: FlightPreferences;
}

export interface HotelPreferences {
  status: "need_search" | "already_have";
  starRating: string;
  roomType: string;
  amenities: string[];
}

export interface FlightPreferences {
  status: "need_search" | "already_have";
  cabinClass: string;
  stops: string;
  airline: string;
}

"use client";

import { useState, useCallback } from "react";
import {
  MapPin,
  Heart,
  Gauge,
  Wallet,
  Car,
  MessageSquarePlus,
  Sparkles,
  X,
  Plus,
  User,
  Baby,
  Calendar,
  Plane,
  Hotel,
  Check,
  BabyIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DateRangePicker } from "@/components/date-range-picker";
import CityAutocomplete from "./prompt-builders/city-autocomplete";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HotelModal } from "./prompt-builders/hotel-modal";
import { FlightModal } from "./prompt-builders/flight-modal";
import { PromptBuilderData } from "@/types/prompt-builder";
import { FormField } from "./prompt-builders/form-field";
import { ChipButton } from "./prompt-builders/chip-button";
import { OptionCard } from "./prompt-builders/option-card";
import { NumberStepper } from "./prompt-builders/number-stepper";
import { ToggleOptionCard } from "./prompt-builders/toggle-option-card";
import {
  INTEREST_OPTIONS,
  PACE_OPTIONS,
  BUDGET_OPTIONS,
  TRAVEL_TRANSPORT_OPTIONS,
  LOCAL_TRANSPORT_OPTIONS,
} from "@/constants/prompt-builder";

interface PromptBuilderProps {
  readonly onGenerate: (prompt: string) => void;
  readonly onClose: () => void;
  readonly defaultStartDate?: Date;
  readonly defaultEndDate?: Date;
}

export default function PromptBuilder({
  onGenerate,
  onClose,
  defaultStartDate,
  defaultEndDate,
}: PromptBuilderProps) {
  const [customInterestInput, setCustomInterestInput] = useState("");
  const [hotelModalOpen, setHotelModalOpen] = useState(false);
  const [flightModalOpen, setFlightModalOpen] = useState(false);

  const [data, setData] = useState<PromptBuilderData>({
    origin: "",
    destination: "",
    travelTransport: "",
    customTravelTransport: "",
    localTransport: "",
    customLocalTransport: "",
    startDate: defaultStartDate ?? null,
    endDate: defaultEndDate ?? null,
    adults: 2,
    children: 0,
    infants: 0,
    interests: [],
    pace: "moderate",
    budgetLevel: "moderate",
    additionalRequests: "",
    needHotel: false,
    needFlight: false,
    hotelPreferences: {
      status: "need_search",
      starRating: "",
      roomType: "",
      amenities: [],
    },
    flightPreferences: {
      status: "need_search",
      cabinClass: "",
      stops: "",
      airline: "",
    },
  });

  // Track custom interests separately to allow removal
  const [customInterests, setCustomInterests] = useState<string[]>([]);
  const allInterestOptions = [...INTEREST_OPTIONS, ...customInterests];

  const updateField = <K extends keyof PromptBuilderData>(
    key: K,
    value: PromptBuilderData[K],
  ) => {
    setData((prev) => ({ ...prev, [key]: value }));
  };

  const toggleInterest = (interest: string) => {
    setData((prev) => ({
      ...prev,
      interests: prev.interests.includes(interest)
        ? prev.interests.filter((i) => i !== interest)
        : [...prev.interests, interest],
    }));
  };

  const addCustomInterest = () => {
    const trimmed = customInterestInput.trim();
    if (
      trimmed &&
      !allInterestOptions
        .map((i) => i.toLowerCase())
        .includes(trimmed.toLowerCase())
    ) {
      setCustomInterests((prev) => [...prev, trimmed]);
      setData((prev) => ({
        ...prev,
        interests: [...prev.interests, trimmed],
      }));
      setCustomInterestInput("");
    }
  };

  const removeCustomInterest = (interest: string) => {
    setCustomInterests((prev) => prev.filter((i) => i !== interest));
    setData((prev) => ({
      ...prev,
      interests: prev.interests.filter((i) => i !== interest),
    }));
  };

  const handleCustomInterestKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCustomInterest();
    }
  };

  const formatDate = (date: Date | null) => {
    if (!date) return "";
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const getTransportLabel = (value: string, customValue: string) => {
    if (value === "other") return customValue;
    if (value === "any") return "any transportation";
    return (
      TRAVEL_TRANSPORT_OPTIONS.find((t) => t.value === value)?.label ?? value
    );
  };

  const getLocalTransportLabel = (value: string, customValue: string) => {
    if (value === "same_as_travel") return null;
    if (value === "other") return customValue;
    if (value === "any") return "any transportation";
    return (
      LOCAL_TRANSPORT_OPTIONS.find((t) => t.value === value)?.label ?? value
    );
  };

  const buildPrompt = useCallback(() => {
    const parts: string[] = [];

    const addIf = (condition: unknown, text: string) => {
      if (condition) parts.push(text);
    };

    // Origin → Destination with transport
    if (data.origin && data.destination && data.travelTransport) {
      parts.push(
        `I want to travel from ${data.origin} to ${data.destination} by ${getTransportLabel(data.travelTransport, data.customTravelTransport)}.`,
      );
    } else if (data.origin && data.destination) {
      parts.push(
        `I want to travel from ${data.origin} to ${data.destination}.`,
      );
    } else if (data.destination) {
      parts.push(`I want to travel to ${data.destination}.`);
    }

    // Local transport
    if (data.localTransport) {
      if (data.localTransport === "same_as_travel" && data.travelTransport) {
        parts.push(
          `I will also use ${getTransportLabel(data.travelTransport, data.customTravelTransport)} to move between tourist spots.`,
        );
      } else {
        const localLabel = getLocalTransportLabel(
          data.localTransport,
          data.customLocalTransport,
        );
        if (localLabel) {
          parts.push(
            `For getting around between tourist spots, I prefer ${localLabel}.`,
          );
        }
      }
    }

    if (data.startDate && data.endDate) {
      parts.push(
        `From ${formatDate(data.startDate)} to ${formatDate(data.endDate)}.`,
      );
    }

    const people: string[] = [];
    if (data.adults > 0)
      people.push(`${data.adults} adult${data.adults > 1 ? "s" : ""}`);
    if (data.children > 0)
      people.push(`${data.children} child${data.children > 1 ? "ren" : ""}`);
    if (data.infants > 0)
      people.push(`${data.infants} infant${data.infants > 1 ? "s" : ""}`);
    if (people.length > 0) {
      const total = data.adults + data.children + data.infants;
      parts.push(
        `Traveling with ${total} ${total > 1 ? "people" : "person"} (${people.join(", ")}).`,
      );
    }

    addIf(data.interests.length, `Interests: ${data.interests.join(", ")}.`);
    addIf(data.pace, `Preferred pace: ${data.pace}.`);
    addIf(data.budgetLevel, `Budget level: ${data.budgetLevel}.`);

    // Hotel preferences
    if (data.needHotel) {
      if (data.hotelPreferences.status === "already_have") {
        parts.push("I already have hotel accommodation arranged.");
      } else {
        const hotelParts: string[] = [];
        if (
          data.hotelPreferences.starRating &&
          data.hotelPreferences.starRating !== "any"
        )
          hotelParts.push(`${data.hotelPreferences.starRating}-star`);
        if (
          data.hotelPreferences.roomType &&
          data.hotelPreferences.roomType !== "any"
        )
          hotelParts.push(`${data.hotelPreferences.roomType} room`);
        if (data.hotelPreferences.amenities.length > 0)
          hotelParts.push(`with ${data.hotelPreferences.amenities.join(", ")}`);
        parts.push(
          `I need hotel recommendations${hotelParts.length > 0 ? `: ${hotelParts.join(", ")}` : ""}.`,
        );
      }
    }

    // Flight preferences
    if (data.needFlight) {
      if (data.flightPreferences.status === "already_have") {
        parts.push("I already have flight tickets booked.");
      } else {
        const flightParts: string[] = [];
        if (
          data.flightPreferences.cabinClass &&
          data.flightPreferences.cabinClass !== "any"
        )
          flightParts.push(`${data.flightPreferences.cabinClass} class`);
        if (
          data.flightPreferences.stops &&
          data.flightPreferences.stops !== "any"
        )
          flightParts.push(data.flightPreferences.stops.replace("_", " "));
        if (data.flightPreferences.airline)
          flightParts.push(`preferably ${data.flightPreferences.airline}`);
        parts.push(
          `I need flight suggestions${flightParts.length > 0 ? `: ${flightParts.join(", ")}` : ""}.`,
        );
      }
    }

    addIf(
      data.additionalRequests,
      `Additional requests: ${data.additionalRequests}`,
    );

    parts.push("Please create a detailed day-by-day itinerary for me.");
    return parts.join(" ");
  }, [data]);

  const handleGenerate = () => {
    onGenerate(buildPrompt());
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden rounded-xl border-2 border-gray-200 bg-white shadow-inner animate-in fade-in duration-200 min-h-0">
      {/* Header */}
      <div className="w-full flex items-center justify-between px-3 py-2 bg-gray-50">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          <span className="text-xs font-semibold text-gray-700">
            Prompt Builder
          </span>
          {data.destination && (
            <span className="text-[10px] text-gray-400 ml-1">
              — {data.destination}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-0.5 rounded hover:bg-gray-200 transition-colors"
        >
          <X className="w-3 h-3 text-gray-400" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 px-3 py-3 space-y-3 overflow-y-auto custom-scrollbar min-h-0">
        {/* 1. Origin → Destination with Transport (Vertical layout) */}
        <FormField
          label="Route"
          required
          icon={<MapPin className="w-3.5 h-3.5" />}
        >
          <div className="flex flex-col relative pl-[4.5rem]">
            {/* Origin */}
            <div className="relative z-30">
              <span className="absolute -left-[4.5rem] top-[6px] text-[10px] font-medium text-gray-500 w-16 text-right">
                Departure
              </span>
              <CityAutocomplete
                value={data.origin}
                onChange={(city) => updateField("origin", city)}
                placeholder="e.g. Hanoi, Bắc Ninh..."
              />
            </div>

            {/* Vertical Connecting Line with Dropdown */}
            <div className="relative py-2 pl-[9px] z-20">
              {/* The dashed vertical line itself */}
              <div className="absolute left-0 top-0 bottom-0 w-px border-l-2 border-dashed border-gray-200 -translate-x-1/2" />

              <div className="relative bg-white z-10 inline-flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500">
                  Travel By
                </span>
                <Select
                  value={data.travelTransport}
                  onValueChange={(v) => updateField("travelTransport", v)}
                >
                  <SelectTrigger
                    size="sm"
                    className="h-7 text-xs w-auto min-w-[140px] border-blue-200 bg-blue-50/50"
                  >
                    <SelectValue placeholder="Choose transportation" />
                  </SelectTrigger>
                  <SelectContent position="popper" side="bottom">
                    {TRAVEL_TRANSPORT_OPTIONS.map((opt) => (
                      <SelectItem
                        key={opt.value}
                        value={opt.value}
                        className="text-xs"
                      >
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Custom Travel Transport Input */}
              {data.travelTransport === "other" && (
                <div className="mt-2 pl-3 relative bg-white z-10 w-full animate-in fade-in slide-in-from-top-1">
                  <input
                    type="text"
                    value={data.customTravelTransport}
                    onChange={(e) =>
                      updateField("customTravelTransport", e.target.value)
                    }
                    placeholder="Specify transport..."
                    className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              )}
            </div>

            {/* Destination */}
            <div className="relative z-10">
              <span className="absolute -left-[4.5rem] top-[6px] text-[10px] font-medium text-gray-500 w-16 text-right">
                Destination
              </span>
              <CityAutocomplete
                value={data.destination}
                onChange={(city) => updateField("destination", city)}
                placeholder="e.g. Ho Chi Minh, Da Nang..."
              />
            </div>
          </div>
        </FormField>

        {/* 2. Local Transport */}
        <FormField
          label="Transportation at destination"
          icon={<Car className="w-3.5 h-3.5" />}
        >
          <Select
            value={data.localTransport}
            onValueChange={(v) => updateField("localTransport", v)}
          >
            <SelectTrigger size="sm" className="w-full text-xs">
              <SelectValue placeholder="How to get around at destination..." />
            </SelectTrigger>
            <SelectContent position="popper" side="bottom">
              {LOCAL_TRANSPORT_OPTIONS.map((opt) => (
                <SelectItem
                  key={opt.value}
                  value={opt.value}
                  className="text-xs"
                >
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {data.localTransport === "other" && (
            <div className="mt-1.5 animate-in fade-in slide-in-from-top-1">
              <input
                type="text"
                value={data.customLocalTransport}
                onChange={(e) =>
                  updateField("customLocalTransport", e.target.value)
                }
                placeholder="Specify local transport..."
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          )}
        </FormField>

        {/* 3. Date Range */}
        <FormField
          label="Travel dates"
          icon={<Calendar className="w-3.5 h-3.5" />}
        >
          <DateRangePicker
            startDate={data.startDate}
            endDate={data.endDate}
            onChange={(start, end) => {
              updateField("startDate", start);
              updateField("endDate", end);
            }}
            className="text-sm h-9"
          />
        </FormField>

        {/* 4. Travelers */}
        <div className="grid grid-cols-3 gap-3">
          <FormField label="Adults" icon={<User className="w-3.5 h-3.5" />}>
            <NumberStepper
              value={data.adults}
              min={1}
              max={20}
              onChange={(v) => updateField("adults", v)}
            />
          </FormField>
          <FormField label="Children" icon={<Baby className="w-3.5 h-3.5" />}>
            <NumberStepper
              value={data.children}
              min={0}
              max={10}
              onChange={(v) => updateField("children", v)}
            />
          </FormField>
          <FormField
            label="Infants"
            icon={<BabyIcon className="w-3.5 h-3.5" />}
          >
            <NumberStepper
              value={data.infants}
              min={0}
              max={5}
              onChange={(v) => updateField("infants", v)}
            />
          </FormField>
        </div>

        {/* 5. Hotel & Flight */}
        <FormField
          label="Hotel & Flight"
          icon={<Plane className="w-3.5 h-3.5" />}
        >
          <div className="flex gap-1.5">
            <ToggleOptionCard
              icon={<Hotel className="w-4 h-4 text-amber-500" />}
              label="Hotel"
              desc={
                data.needHotel
                  ? data.hotelPreferences.status === "already_have"
                    ? "Already booked"
                    : "Finding hotel"
                  : "Click to add"
              }
              active={data.needHotel}
              configured={data.needHotel}
              onClick={() => {
                if (data.needHotel) {
                  setHotelModalOpen(true);
                } else {
                  updateField("needHotel", true);
                  setHotelModalOpen(true);
                }
              }}
              onRemove={() => updateField("needHotel", false)}
            />
            <ToggleOptionCard
              icon={<Plane className="w-4 h-4 text-sky-500" />}
              label="Flight"
              desc={
                data.needFlight
                  ? data.flightPreferences.status === "already_have"
                    ? "Already booked"
                    : "Finding flight"
                  : "Click to add"
              }
              active={data.needFlight}
              configured={data.needFlight}
              onClick={() => {
                if (data.needFlight) {
                  setFlightModalOpen(true);
                } else {
                  updateField("needFlight", true);
                  setFlightModalOpen(true);
                }
              }}
              onRemove={() => updateField("needFlight", false)}
            />
          </div>
        </FormField>

        {/* 6. Pace */}
        <FormField label="Travel pace" icon={<Gauge className="w-3.5 h-3.5" />}>
          <div className="flex gap-1.5">
            {PACE_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              return (
                <OptionCard
                  key={opt.value}
                  icon={<Icon className={cn("w-4 h-4", opt.iconClass)} />}
                  label={opt.label}
                  desc={opt.desc}
                  selected={data.pace === opt.value}
                  onClick={() =>
                    updateField(
                      "pace",
                      data.pace === opt.value ? "" : opt.value,
                    )
                  }
                />
              );
            })}
          </div>
        </FormField>

        {/* 7. Budget */}
        <FormField
          label="Budget level"
          icon={<Wallet className="w-3.5 h-3.5" />}
        >
          <div className="flex gap-1.5">
            {BUDGET_OPTIONS.map((opt) => (
              <OptionCard
                key={opt.value}
                icon={<span className="text-base">{opt.icon}</span>}
                label={opt.label}
                desc={opt.desc}
                selected={data.budgetLevel === opt.value}
                onClick={() =>
                  updateField(
                    "budgetLevel",
                    data.budgetLevel === opt.value ? "" : opt.value,
                  )
                }
              />
            ))}
          </div>
        </FormField>

        {/* 8. Interests */}
        <FormField label="Interests" icon={<Heart className="w-3.5 h-3.5" />}>
          <div className="flex flex-wrap gap-1.5">
            {allInterestOptions.map((interest) => (
              <ChipButton
                key={interest}
                label={interest}
                selected={data.interests.includes(interest)}
                onClick={() => toggleInterest(interest)}
                onRemove={
                  customInterests.includes(interest)
                    ? () => removeCustomInterest(interest)
                    : undefined
                }
              />
            ))}
          </div>
          {/* Add custom interest */}
          <div className="flex items-center gap-1.5 mt-1.5">
            <input
              type="text"
              value={customInterestInput}
              onChange={(e) => setCustomInterestInput(e.target.value)}
              onKeyDown={handleCustomInterestKeyDown}
              placeholder="Add custom interest..."
              className="flex-1 px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              type="button"
              onClick={addCustomInterest}
              disabled={!customInterestInput.trim()}
              className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 hover:text-blue-600 disabled:opacity-30 transition-colors"
            >
              <Plus className="w-3 h-3" />
            </button>
          </div>
        </FormField>

        {/* 9. Additional requests */}
        <FormField
          label="Anything else?"
          icon={<MessageSquarePlus className="w-3.5 h-3.5" />}
        >
          <textarea
            value={data.additionalRequests}
            onChange={(e) => updateField("additionalRequests", e.target.value)}
            placeholder="Special requests, must-visit places, things to avoid..."
            rows={2}
            className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </FormField>
      </div>

      {/* Footer — Generate button */}
      <div className="px-3 py-2 flex justify-end">
        <Button
          size="sm"
          onClick={handleGenerate}
          disabled={!data.destination.trim()}
          className="text-xs bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white"
        >
          <Sparkles className="w-3 h-3 mr-1" />
          Generate
        </Button>
      </div>

      {/* Modals */}
      <HotelModal
        open={hotelModalOpen}
        onOpenChange={setHotelModalOpen}
        preferences={data.hotelPreferences}
        onConfirm={(prefs) => updateField("hotelPreferences", prefs)}
      />
      <FlightModal
        open={flightModalOpen}
        onOpenChange={setFlightModalOpen}
        preferences={data.flightPreferences}
        onConfirm={(prefs) => updateField("flightPreferences", prefs)}
      />
    </div>
  );
}

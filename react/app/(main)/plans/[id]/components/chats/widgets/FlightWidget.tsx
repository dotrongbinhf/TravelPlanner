import React from "react";
import { Plane, ExternalLink, CircleCheck, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface FlightWidgetProps {
  data: any;
}

export function FlightWidget({ data }: FlightWidgetProps) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 flex items-center justify-center gap-3 animate-pulse my-4 shadow-sm">
        <div className="w-5 h-5 rounded-full border-[3px] border-blue-500 border-t-transparent animate-spin" />
        <span className="text-[15px] font-semibold text-slate-600 tracking-tight">
          Searching for the best flights...
        </span>
      </div>
    );
  }

  const formatPrice = (price: number | string) => {
    if (!price) return "";
    if (typeof price === "number") {
      return new Intl.NumberFormat("vi-VN").format(price) + " đ";
    }
    return String(price);
  };

  const formatDuration = (min: number) => {
    if (!min) return "";
    const h = Math.floor(min / 60);
    const m = min % 60;
    return `${h}h${m > 0 ? ` ${m}m` : ""}`;
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", { day: "numeric", month: "short" });
    } catch {
      return dateStr;
    }
  };

  const outbound = data.recommend_outbound_flight;
  const returnFlight = data.recommend_return_flight;

  if (!outbound && !returnFlight) return null;

  const isRoundTrip = data.type === "round_trip";

  // Passenger label
  const passengers = data.passengers || {};
  const passengerParts: string[] = [];
  if (passengers.adults > 0)
    passengerParts.push(
      `${passengers.adults} adult${passengers.adults > 1 ? "s" : ""}`,
    );
  if (passengers.children > 0)
    passengerParts.push(
      `${passengers.children} child${passengers.children > 1 ? "ren" : ""}`,
    );
  if (passengers.infants_in_seat > 0)
    passengerParts.push(`${passengers.infants_in_seat} infant in seat`);
  if (passengers.infants_on_lap > 0)
    passengerParts.push(`${passengers.infants_on_lap} infant on lap`);
  const passengerLabel =
    passengerParts.length > 0 ? passengerParts.join(", ") : "";

  // Split alternatives by direction
  const outboundAlts = (data.alternatives || [])
    .filter((a: any) => a.direction === "outbound" || !a.direction)
    .slice(0, 2);
  const returnAlts = (data.alternatives || [])
    .filter((a: any) => a.direction === "return")
    .slice(0, 2);

  // Compact flight row
  const FlightRow = ({
    flight,
    isRecommended,
    showPrice = true,
  }: {
    flight: any;
    isRecommended: boolean;
    showPrice?: boolean;
  }) => {
    const depTime =
      (flight.departure_time || "").split(" ").pop() ||
      flight.departure_time ||
      "";
    const arrTime =
      (flight.arrival_time || "").split(" ").pop() || flight.arrival_time || "";
    const depId = flight.departure_airport_id || "";
    const arrId = flight.arrival_airport_id || "";
    const fn = flight.flight_number || "";
    const airline = flight.airline || "";
    const airlineLogo = flight.airline_logo || "";
    const dur = flight.total_duration_min;
    const stops = flight.stops ?? 0;
    const stopsLabel =
      stops === 0 ? "Nonstop" : `${stops} stop${stops > 1 ? "s" : ""}`;

    return (
      <div
        className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg border transition-all duration-150 ${
          isRecommended
            ? "border-sky-200 bg-sky-50/60"
            : "border-slate-100 bg-white hover:bg-slate-50/50"
        }`}
      >
        {/* Airline logo or icon */}
        <div className="w-7 h-7 shrink-0 rounded-full overflow-hidden bg-slate-100 flex items-center justify-center">
          {airlineLogo ? (
            <img
              src={airlineLogo}
              alt={airline}
              className="w-full h-full object-contain"
            />
          ) : (
            <Plane className="w-3.5 h-3.5 text-slate-400" />
          )}
        </div>

        {/* Time + airline */}
        <div className="w-[110px] shrink-0">
          <div
            className={`text-[14px] tracking-tight leading-tight ${isRecommended ? "font-extrabold text-slate-900" : "font-bold text-slate-700"}`}
          >
            {depTime} — {arrTime}
          </div>
          <div className="text-[11px] font-medium text-slate-400 mt-0.5 truncate">
            {fn}
            {airline ? ` · ${airline}` : ""}
          </div>
        </div>

        {/* Route */}
        <div className="flex items-center gap-1.5 w-[80px] shrink-0">
          <span className="text-[12px] font-semibold text-slate-600">
            {depId}
          </span>
          <ArrowRight className="w-3 h-3 text-slate-300" />
          <span className="text-[12px] font-semibold text-slate-600">
            {arrId}
          </span>
        </div>

        {/* Duration + stops */}
        <div className="flex-1 min-w-0">
          <div className="text-[12px] font-medium text-slate-500">
            {stopsLabel}
          </div>
          {dur > 0 && (
            <div className="text-[11px] text-slate-400 mt-0.5">
              {formatDuration(dur)}
            </div>
          )}
        </div>

        {/* Price */}
        {showPrice && flight.price ? (
          <div className="text-right shrink-0">
            <div
              className={`text-[13px] ${isRecommended ? "font-extrabold text-sky-700" : "font-bold text-slate-600"}`}
            >
              {formatPrice(flight.price)}
            </div>
          </div>
        ) : null}

        {/* Recommend badge */}
        {isRecommended && (
          <div className="shrink-0">
            <CircleCheck className="w-4 h-4 text-sky-500" />
          </div>
        )}
      </div>
    );
  };

  // Google Flights link button
  const GFlightsLink = ({ url }: { url: string }) => (
    <Button
      variant="outline"
      size="sm"
      className="rounded-full text-[11px] font-bold text-slate-500 border-slate-200 hover:bg-slate-50 h-7 px-3"
      onClick={() => window.open(url, "_blank")}
    >
      <ExternalLink className="w-3 h-3 mr-1.5 text-slate-400" />
      Google Flights
    </Button>
  );

  // Section header with direction label
  const SectionLabel = ({
    label,
    priceLabel,
    isBold = false,
  }: {
    label: string;
    priceLabel?: string;
    isBold?: boolean;
  }) => (
    <div className="flex items-center justify-between px-1 mb-1.5">
      <h4
        className={`text-[11px] uppercase tracking-widest ${isBold ? "font-extrabold text-sky-600" : "font-bold text-slate-400"}`}
      >
        {label}
      </h4>
      {priceLabel && (
        <span
          className={`text-[13px] ${isBold ? "font-extrabold text-sky-700" : "font-bold text-slate-500"}`}
        >
          {priceLabel}
        </span>
      )}
    </div>
  );

  // Header subtitle
  const headerSubtitle = (() => {
    const depId =
      outbound?.departure_airport_id || returnFlight?.arrival_airport_id || "";
    const arrId =
      outbound?.arrival_airport_id || returnFlight?.departure_airport_id || "";
    const route = depId && arrId ? `${depId} → ${arrId}` : "";
    const typeLabel = isRoundTrip ? "Round trip" : "One way";
    const dateLabel = (() => {
      const out = formatDate(data.outbound_date);
      const ret = formatDate(data.return_date);
      if (out && ret && isRoundTrip) return `${out} – ${ret}`;
      if (out) return out;
      return "";
    })();
    return [typeLabel, route, dateLabel, passengerLabel]
      .filter(Boolean)
      .join(" · ");
  })();

  return (
    <div className="w-full my-4 rounded-2xl border border-slate-200 shadow-sm bg-white overflow-hidden">
      {/* Header — styled like HotelWidget */}
      <div className="px-5 py-3 rounded-t-xl bg-sky-50 text-sky-900 border-b border-sky-100 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg overflow-hidden bg-white flex items-center justify-center shrink-0">
          <img
            src="/images/plans/serpapi.png"
            alt="SerpApi"
            className="w-full h-full object-cover"
          />
        </div>
        <div className="min-w-0">
          <h3 className="font-bold text-[15px] tracking-tight">
            SerpAPI - Google Flights
          </h3>
          <p className="text-[11px] text-sky-900 font-medium truncate">
            {headerSubtitle}
          </p>
        </div>
      </div>

      <div className="p-3.5 space-y-4 bg-white">
        {isRoundTrip ? (
          /* ── ROUND TRIP ── */
          <>
            {/* Recommended pair */}
            <div className="space-y-1.5">
              <SectionLabel
                label="✈ Recommended"
                priceLabel={
                  data.totalPrice ? formatPrice(data.totalPrice) : undefined
                }
                isBold
              />
              {outbound && (
                <FlightRow
                  flight={outbound}
                  isRecommended={true}
                  showPrice={false}
                />
              )}
              {returnFlight && (
                <FlightRow
                  flight={returnFlight}
                  isRecommended={true}
                  showPrice={false}
                />
              )}
            </div>

            {/* Other outbound options */}
            {outboundAlts.length > 0 && (
              <div className="space-y-1.5">
                <SectionLabel label="Other Options" />
                {outboundAlts.map((alt: any, idx: number) => (
                  <FlightRow
                    key={`out-alt-${idx}`}
                    flight={alt}
                    isRecommended={false}
                  />
                ))}
              </div>
            )}

            {/* Single Google Flights link for roundtrip */}
            {data.google_flights_url && (
              <div className="pt-2 border-t border-slate-100 flex justify-end">
                <GFlightsLink url={data.google_flights_url} />
              </div>
            )}
          </>
        ) : (
          /* ── ONE-WAY / BOTH DIRECTIONS ── */
          <>
            {/* Outbound section */}
            {outbound && (
              <div className="space-y-1.5">
                <SectionLabel label="✈ Outbound" isBold />
                <FlightRow flight={outbound} isRecommended={true} />
                {outboundAlts.map((alt: any, idx: number) => (
                  <FlightRow
                    key={`out-alt-${idx}`}
                    flight={alt}
                    isRecommended={false}
                  />
                ))}
                {/* Per-direction link */}
                {(outbound.google_flights_url || data.google_flights_url) && (
                  <div className="flex justify-end pt-1">
                    <GFlightsLink
                      url={
                        outbound.google_flights_url || data.google_flights_url
                      }
                    />
                  </div>
                )}
              </div>
            )}

            {/* Return section */}
            {returnFlight && (
              <div className="space-y-1.5">
                <SectionLabel label="✈ Return" isBold />
                <FlightRow flight={returnFlight} isRecommended={true} />
                {returnAlts.map((alt: any, idx: number) => (
                  <FlightRow
                    key={`ret-alt-${idx}`}
                    flight={alt}
                    isRecommended={false}
                  />
                ))}
                {/* Per-direction link */}
                {(returnFlight.google_flights_url ||
                  data.google_flights_url) && (
                  <div className="flex justify-end pt-1">
                    <GFlightsLink
                      url={
                        returnFlight.google_flights_url ||
                        data.google_flights_url
                      }
                    />
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

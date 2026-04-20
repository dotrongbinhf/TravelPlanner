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

  const outbound = data.recommend_outbound_flight;
  const returnFlight = data.recommend_return_flight;

  if (!outbound && !returnFlight) return null;

  const isRoundTrip = data.type === "round_trip";

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
    const depTime = flight.departure_time || "";
    const arrTime = flight.arrival_time || "";
    const depId = flight.departure_airport_id || "";
    const arrId = flight.arrival_airport_id || "";
    const fn = flight.flight_number || "";
    const airline = flight.airline || "";
    const dur = flight.total_duration_min;
    const stops = flight.stops ?? 0;
    const stopsLabel =
      stops === 0 ? "Nonstop" : `${stops} stop${stops > 1 ? "s" : ""}`;

    return (
      <div
        className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg border transition-all duration-150 ${
          isRecommended
            ? "border-sky-200 bg-sky-50/50"
            : "border-slate-100 bg-white hover:bg-slate-50/50"
        }`}
      >
        {/* Recommended indicator */}
        <div className="w-4 shrink-0 flex justify-center">
          {isRecommended && (
            <CircleCheck className="w-3.5 h-3.5 text-sky-500" />
          )}
        </div>

        {/* Time */}
        <div className="w-[110px] shrink-0">
          <div className="text-[14px] font-bold text-slate-900 tracking-tight leading-tight">
            {depTime} — {arrTime}
          </div>
          <div className="text-[11px] font-medium text-slate-400 mt-0.5">
            {fn || airline}
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
            <div className="text-[13px] font-bold text-slate-800">
              {formatPrice(flight.price)}
            </div>
          </div>
        ) : null}
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
    subtitle,
  }: {
    label: string;
    subtitle?: string;
  }) => (
    <div className="flex items-center gap-2 px-1 mb-1.5">
      <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
        {label}
      </h4>
      {subtitle && (
        <span className="text-[10px] text-slate-300 font-medium">
          {subtitle}
        </span>
      )}
    </div>
  );

  // Header subtitle
  const headerSubtitle = (() => {
    const depId =
      outbound?.departure_airport_id ||
      returnFlight?.arrival_airport_id ||
      "";
    const arrId =
      outbound?.arrival_airport_id ||
      returnFlight?.departure_airport_id ||
      "";
    const route = depId && arrId ? `${depId} → ${arrId}` : "";
    const typeLabel = isRoundTrip ? "Round trip" : "One way";
    return [typeLabel, route].filter(Boolean).join(" · ");
  })();

  return (
    <div className="w-full my-4 rounded-2xl border border-slate-200 shadow-sm bg-white overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-slate-900 text-white flex items-center gap-3">
        <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center">
          <Plane className="w-3.5 h-3.5 text-white" />
        </div>
        <div>
          <h3 className="font-bold text-[13px] tracking-tight">
            Flight Options
          </h3>
          <p className="text-[10px] text-white/60 font-medium">
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
              <SectionLabel label="Recommended" subtitle={data.totalPrice ? formatPrice(data.totalPrice) : undefined} />
              {outbound && <FlightRow flight={outbound} isRecommended={true} showPrice={false} />}
              {returnFlight && <FlightRow flight={returnFlight} isRecommended={true} showPrice={false} />}
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
                <SectionLabel label="Outbound" />
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
                      url={outbound.google_flights_url || data.google_flights_url}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Return section */}
            {returnFlight && (
              <div className="space-y-1.5">
                <SectionLabel label="Return" />
                <FlightRow flight={returnFlight} isRecommended={true} />
                {returnAlts.map((alt: any, idx: number) => (
                  <FlightRow
                    key={`ret-alt-${idx}`}
                    flight={alt}
                    isRecommended={false}
                  />
                ))}
                {/* Per-direction link */}
                {(returnFlight.google_flights_url || data.google_flights_url) && (
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

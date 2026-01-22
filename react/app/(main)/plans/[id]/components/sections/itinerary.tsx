"use client";

import { forwardRef } from "react";

interface ItineraryProps {
  className?: string;
}

const Itinerary = forwardRef<HTMLDivElement, ItineraryProps>(function Itinerary(
  { className },
  ref
) {
  return (
    <section
      ref={ref}
      id="itinerary"
      data-section-id="itinerary"
      className={className}
    >
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Itinerary</h2>
      <div className="bg-gray-50 rounded-lg p-4 min-h-[300px]">
        <p className="text-gray-400 text-sm">
          Itinerary component - Coming soon...
        </p>
      </div>
    </section>
  );
});

export default Itinerary;

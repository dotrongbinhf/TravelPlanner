"use client";

import { forwardRef } from "react";

interface PackingListsProps {
  className?: string;
}

const PackingLists = forwardRef<HTMLDivElement, PackingListsProps>(
  function PackingLists({ className }, ref) {
    return (
      <section
        ref={ref}
        id="packing-lists"
        data-section-id="packing-lists"
        className={className}
      >
        <h2 className="text-xl font-semibold text-gray-800 mb-4">
          Packing Lists
        </h2>
        <div className="bg-gray-50 rounded-lg p-4 min-h-[300px]">
          <p className="text-gray-400 text-sm">
            Packing Lists component - Coming soon...
          </p>
        </div>
      </section>
    );
  }
);

export default PackingLists;

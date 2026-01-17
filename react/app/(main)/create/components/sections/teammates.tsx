"use client";

import { forwardRef } from "react";

interface TeammatesProps {
  className?: string;
}

const Teammates = forwardRef<HTMLDivElement, TeammatesProps>(function Teammates(
  { className },
  ref
) {
  return (
    <section
      ref={ref}
      id="teammates"
      data-section-id="teammates"
      className={className}
    >
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Teammates</h2>
      <div className="bg-gray-50 rounded-lg p-4 min-h-[300px]">
        <p className="text-gray-400 text-sm">
          Teammates component - Coming soon...
        </p>
      </div>
    </section>
  );
});

export default Teammates;

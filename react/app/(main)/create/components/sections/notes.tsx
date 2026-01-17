"use client";

import { forwardRef } from "react";

interface NotesProps {
  className?: string;
}

const Notes = forwardRef<HTMLDivElement, NotesProps>(function Notes(
  { className },
  ref
) {
  return (
    <section ref={ref} id="notes" data-section-id="notes" className={className}>
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Notes</h2>
      <div className="bg-gray-50 rounded-lg p-4 min-h-[300px]">
        <p className="text-gray-400 text-sm">
          Notes component - Coming soon...
        </p>
      </div>
    </section>
  );
});

export default Notes;

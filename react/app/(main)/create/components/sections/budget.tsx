"use client";

import { forwardRef } from "react";

interface BudgetProps {
  className?: string;
}

const Budget = forwardRef<HTMLDivElement, BudgetProps>(function Budget(
  { className },
  ref
) {
  return (
    <section
      ref={ref}
      id="budget"
      data-section-id="budget"
      className={className}
    >
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Budget</h2>
      <div className="bg-gray-50 rounded-lg p-4 min-h-[300px]">
        <p className="text-gray-400 text-sm">
          Budget component - Coming soon...
        </p>
      </div>
    </section>
  );
});

export default Budget;

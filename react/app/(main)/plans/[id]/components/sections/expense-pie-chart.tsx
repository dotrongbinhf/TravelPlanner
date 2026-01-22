import { Expense, EXPENSE_CATEGORIES, ExpenseCategory } from "@/types/budget";

interface ExpensePieChartProps {
  expenses: Expense[];
}

export default function ExpensePieChart({ expenses }: ExpensePieChartProps) {
  // Group expenses by category
  const categoryTotals = EXPENSE_CATEGORIES.map((cat) => {
    const total = expenses
      .filter((e) => e.category === cat.value)
      .reduce((sum, e) => sum + e.amount, 0);
    return {
      ...cat,
      total,
    };
  }).filter((cat) => cat.total > 0);

  const totalAmount = categoryTotals.reduce((sum, cat) => sum + cat.total, 0);

  if (totalAmount === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-400">
        <div className="w-32 h-32 rounded-full border-4 border-dashed border-gray-300 flex items-center justify-center">
          <span className="text-sm">No data</span>
        </div>
      </div>
    );
  }

  // Calculate pie chart segments
  let cumulativePercent = 0;
  const segments = categoryTotals.map((cat) => {
    const percent = (cat.total / totalAmount) * 100;
    const startPercent = cumulativePercent;
    cumulativePercent += percent;
    return {
      ...cat,
      percent,
      startPercent,
    };
  });

  // Create conic gradient
  const gradientStops = segments
    .map(
      (seg) =>
        `${seg.color} ${seg.startPercent}% ${seg.startPercent + seg.percent}%`,
    )
    .join(", ");

  return (
    <div className="flex flex-col gap-4">
      <h3 className="font-semibold text-base text-gray-800">
        Expense Breakdown
      </h3>

      <div className="flex items-center gap-6">
        {/* Pie Chart */}
        <div
          className="w-32 h-32 rounded-full"
          style={{
            background: `conic-gradient(${gradientStops})`,
          }}
        />

        {/* Legend */}
        <div className="flex flex-col gap-2">
          {segments.map((seg) => (
            <div key={seg.value} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: seg.color }}
              />
              <span className="text-sm text-gray-600">{seg.label}</span>
              <span className="text-sm font-medium text-gray-800">
                ${seg.total.toFixed(2)} ({seg.percent.toFixed(1)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

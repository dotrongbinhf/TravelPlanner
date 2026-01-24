"use client";

import { Pie, PieChart } from "recharts";
import {
  ExpenseItem,
  EXPENSE_CATEGORIES,
  ExpenseCategory,
} from "@/types/budget";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { useMemo } from "react";

interface ExpenseChartProps {
  expenseItems: ExpenseItem[];
  currencySymbol: string;
  currencyLocale: string;
}

export function ExpenseChart({
  expenseItems,
  currencySymbol,
  currencyLocale,
}: ExpenseChartProps) {
  // Group expenses by category and calculate totals
  const { chartData, chartConfig, segments, totalAmount } = useMemo(() => {
    const categoryTotals = EXPENSE_CATEGORIES.map((cat) => {
      const total = expenseItems
        .filter((e) => e.category === cat.value)
        .reduce((sum, e) => sum + e.amount, 0);
      return {
        ...cat,
        total,
      };
    }).filter((cat) => cat.total > 0);

    const totalAmount = categoryTotals.reduce((sum, cat) => sum + cat.total, 0);

    // Calculate percentages for legend
    const segments = categoryTotals.map((cat) => ({
      ...cat,
      percent: totalAmount > 0 ? (cat.total / totalAmount) * 100 : 0,
    }));

    // Build chart data for Recharts
    const chartData = categoryTotals.map((cat) => ({
      category: cat.label,
      amount: cat.total,
      fill: cat.color,
    }));

    // Build chart config for Recharts
    const chartConfig: ChartConfig = {
      amount: {
        label: "Amount",
      },
      ...Object.fromEntries(
        categoryTotals.map((cat) => [
          cat.label,
          {
            label: cat.label,
            color: cat.color,
          },
        ]),
      ),
    };

    return { chartData, chartConfig, segments, totalAmount };
  }, [expenseItems]);

  if (totalAmount === 0) {
    return (
      <div className="flex flex-col gap-4">
        <h3 className="font-semibold text-base text-gray-800">
          Expense Breakdown
        </h3>
        <div className="flex flex-col items-center justify-center py-8 text-gray-400">
          <div className="w-40 h-40 rounded-full border-4 border-dashed border-gray-300 flex items-center justify-center">
            <span className="text-sm">No data</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="font-semibold text-base text-gray-800">
        Expense Breakdown
      </h3>

      <div className="flex items-center">
        {/* Pie Chart */}
        <ChartContainer
          config={chartConfig}
          className="aspect-square h-[200px]"
        >
          <PieChart>
            <ChartTooltip
              cursor={false}
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const data = payload[0];
                const categoryName = data.name as string;
                const amount = data.value as number;
                const color = data.payload?.fill;

                return (
                  <div className="bg-white border border-gray-200 rounded-md shadow-md px-2 py-1 flex items-center gap-1.5">
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-xs text-gray-700">
                      {categoryName}{" "}
                      <span className="font-medium">
                        {currencySymbol}
                        {amount.toLocaleString(currencyLocale)}
                      </span>
                    </span>
                  </div>
                );
              }}
            />
            <Pie
              data={chartData}
              dataKey="amount"
              nameKey="category"
              innerRadius={0}
              strokeWidth={2}
            />
          </PieChart>
        </ChartContainer>

        {/* Legend */}
        <div className="flex flex-col gap-2">
          {segments.map((seg) => (
            <div key={seg.value} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: seg.color }}
              />
              <span className="text-sm text-gray-600">{seg.label}</span>
              <span className="text-sm font-medium text-gray-800">
                {currencySymbol}
                {seg.total.toLocaleString(currencyLocale)} (
                {seg.percent.toFixed(1)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

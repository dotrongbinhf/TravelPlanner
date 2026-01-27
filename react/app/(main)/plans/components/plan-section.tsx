"use client";

import { Plan } from "@/types/plan";
import PlanCard from "./plan-card";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PaginatedResult } from "@/types/paginated";
import PlanCardSkeleton from "./plan-card-skeleton";

interface PlanSectionProps {
  title: string;
  icon?: React.ReactNode;
  data: PaginatedResult<Plan> | null;
  isLoading: boolean;
  variant: "owned" | "shared" | "pending";
  emptyMessage: string;
  onPageChange: (page: number) => void;
  onAccept?: (plan: Plan) => void;
  onDecline?: (plan: Plan) => void;
  onDelete?: (plan: Plan) => void;
  onLeave?: (plan: Plan) => void;
}

export default function PlanSection({
  title,
  icon,
  data,
  isLoading,
  variant,
  emptyMessage,
  onPageChange,
  onAccept,
  onDecline,
  onDelete,
  onLeave,
}: PlanSectionProps) {
  if (isLoading) {
    return (
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          {icon}
          <h2 className="text-xl font-bold text-gray-800">{title}</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <PlanCardSkeleton key={i} variant={variant} />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          {icon}
          <h2 className="text-xl font-bold text-gray-800">{title}</h2>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-8 text-center">
          <p className="text-gray-500">{emptyMessage}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {icon}
          <h2 className="text-xl font-bold text-gray-800">{title}</h2>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-4">
        {data.items.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            variant={variant}
            onAccept={onAccept ? () => onAccept(plan) : undefined}
            onDecline={onDecline ? () => onDecline(plan) : undefined}
            onDelete={onDelete ? () => onDelete(plan) : undefined}
            onLeave={onLeave ? () => onLeave(plan) : undefined}
          />
        ))}
      </div>

      <div className="flex items-center justify-center">
        {data.totalPages > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">
              Page {data.page} of {data.totalPages}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => onPageChange(data.page - 1)}
              disabled={data.page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => onPageChange(data.page + 1)}
              disabled={data.page >= data.totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

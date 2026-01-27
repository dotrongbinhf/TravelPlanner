"use client";

import { Skeleton } from "@/components/ui/skeleton";

interface PlanCardSkeletonProps {
  variant: "owned" | "shared" | "pending";
}

export default function PlanCardSkeleton({ variant }: PlanCardSkeletonProps) {
  const cardContent = (
    <div className="relative group rounded-xl overflow-hidden bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all duration-200 h-full flex flex-col">
      {/* Cover Image */}
      <div className="relative h-[224px] w-full overflow-hidden">
        <Skeleton className="w-full h-full" />
      </div>

      {/* Content */}
      <div className="p-4 flex flex-col flex-1">
        <h3 className="font-semibold text-gray-900 text-lg line-clamp-1 mb-2">
          <Skeleton className="w-full h-[28px]" />
        </h3>

        <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
          <Skeleton className="w-full h-[20px]" />
        </div>

        {variant === "pending" && (
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-4 font-medium">
            <Skeleton className="w-full h-[20px]" />
          </div>
        )}

        <div className="mt-auto">
          <Skeleton className="w-full h-[32px] mb-3" />
        </div>

        {variant === "pending" && (
          <div className="flex items-center gap-2 pt-2">
            <Skeleton className="w-full h-[32px]" />
            <Skeleton className="w-full h-[32px]" />
          </div>
        )}
      </div>
    </div>
  );

  return <div className="h-full">{cardContent}</div>;
}

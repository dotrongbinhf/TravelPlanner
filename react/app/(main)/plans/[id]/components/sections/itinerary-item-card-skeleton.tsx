import { Skeleton } from "@/components/ui/skeleton";

export default function ItineraryItemCardSkeleton() {
  return (
    <div className="flex flex-col gap-1 w-full relative">
      {/* Time Header Skeleton */}
      <Skeleton className="h-6 w-24 rounded-md mb-1" />

      {/* Place Card Skeleton */}
      <div className="flex gap-2 p-2 rounded-lg border-2 border-gray-100 bg-white">
        {/* Image placeholder */}
        <Skeleton className="w-20 h-20 rounded-md shrink-0" />

        {/* Content */}
        <div className="flex-1 flex flex-col gap-2 py-1">
          {/* Title */}
          <Skeleton className="h-4 w-3/4" />
          {/* Address */}
          <Skeleton className="h-3 w-full" />
          {/* Rating */}
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
    </div>
  );
}

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ItineraryDayNavigatorProps {
  currentDay: number;
  totalDays: number;
  onPrevious: () => void;
  onNext: () => void;
}

export default function ItineraryDayNavigator({
  currentDay,
  totalDays,
  onPrevious,
  onNext,
}: ItineraryDayNavigatorProps) {
  return (
    <div className="flex items-center gap-2 bg-white backdrop-blur-sm rounded-full shadow-lg p-1 border border-gray-200">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 rounded-full hover:bg-gray-200"
        onClick={onPrevious}
        disabled={currentDay <= 0}
      >
        <ChevronLeft size={16} />
      </Button>
      <span className="text-sm font-semibold text-gray-700 min-w-[60px] text-center">
        Day {currentDay + 1} / {totalDays}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 rounded-full hover:bg-gray-200"
        onClick={onNext}
        disabled={currentDay >= totalDays - 1}
      >
        <ChevronRight size={16} />
      </Button>
    </div>
  );
}

import { AdvancedMarker } from "@vis.gl/react-google-maps";
import { Home, Flag, BedDouble } from "lucide-react";
import { cn } from "@/lib/utils";
import MarkerPin from "./marker-pin";

interface ItineraryMarkerProps {
  position: { lat: number; lng: number };
  orderNumber: number;
  dayColor: string;
  isFirst: boolean;
  isLast: boolean;
  isActive: boolean;
  isBed?: boolean;
  onClick: () => void;
}

export default function ItineraryMarker({
  position,
  orderNumber,
  dayColor,
  isFirst,
  isLast,
  isActive,
  isBed = false,
  onClick,
}: ItineraryMarkerProps) {
  const baseWidth = 30;
  const baseHeight = 42;
  const baseIconSize = 14;

  const renderIcon = () => {
    if (isFirst) {
      return (
        <Home
          size={baseIconSize}
          className="text-white fill-white/20"
          strokeWidth={3}
        />
      );
    }
    if (isBed) {
      return (
        <BedDouble
          size={baseIconSize}
          className="text-white fill-white/20"
          strokeWidth={3}
        />
      );
    }
    if (isLast) {
      return (
        <Flag
          size={baseIconSize}
          className="text-white fill-white/20"
          strokeWidth={3}
        />
      );
    }
    return (
      <span className="font-bold leading-none text-sm">{orderNumber}</span>
    );
  };

  return (
    <AdvancedMarker position={position} onClick={onClick}>
      <div className="relative flex items-center justify-center p-0 m-0">
        <div
          className={cn(
            "relative flex items-center justify-center cursor-pointer transition-transform duration-300 ease-out group origin-bottom",
            isActive
              ? "z-20 scale-125"
              : "z-10 scale-100 hover:scale-110 hover:z-20",
          )}
        >
          <MarkerPin
            width={baseWidth}
            height={baseHeight}
            color={dayColor}
            active={isActive}
          >
            {renderIcon()}
          </MarkerPin>
        </div>
      </div>
    </AdvancedMarker>
  );
}

import { AdvancedMarker } from "@vis.gl/react-google-maps";
import { Hotel, MapPin, UtensilsCrossed } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatPlaceMarkerProps {
  position: { lat: number; lng: number };
  name: string;
  source: "hotel" | "attraction" | "restaurant";
  isActive: boolean;
  onClick: () => void;
}

export default function ChatPlaceMarker({
  position,
  name,
  source,
  isActive,
  onClick,
}: ChatPlaceMarkerProps) {
  const getIconAndColor = () => {
    switch (source) {
      case "hotel":
        return { icon: <Hotel size={14} className="text-white" />, color: "bg-sky-500", borderColor: "border-sky-600" };
      case "attraction":
        return { icon: <MapPin size={14} className="text-white" />, color: "bg-rose-500", borderColor: "border-rose-600" };
      case "restaurant":
        return { icon: <UtensilsCrossed size={14} className="text-white" />, color: "bg-orange-500", borderColor: "border-orange-600" };
    }
  };

  const { icon, color, borderColor } = getIconAndColor();

  return (
    <AdvancedMarker position={position} onClick={onClick} zIndex={isActive ? 100 : 50}>
      <div
        className={cn(
          "relative flex items-center justify-center cursor-pointer transition-all duration-300 ease-out group",
          isActive ? "scale-110" : "scale-100 hover:scale-105"
        )}
      >
        <div className="absolute bottom-full mb-1 flex-col items-center flex opacity-100 transition-opacity duration-200 z-10">
          <div className="bg-white px-2 py-1 rounded-md shadow-md border border-slate-200 text-xs font-bold text-slate-800 whitespace-nowrap text-center max-w-[150px] truncate">
            {name}
          </div>
          <div className="w-2 h-2 bg-white rotate-45 -mt-1.5 border-r border-b border-slate-200"></div>
        </div>

        <div
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center shadow-md border-2",
            color,
            borderColor,
            isActive ? "ring-4 ring-white shadow-xl" : "shadow-sm"
          )}
        >
          {icon}
        </div>
      </div>
    </AdvancedMarker>
  );
}

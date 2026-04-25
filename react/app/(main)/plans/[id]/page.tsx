"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import GoogleMapIntegration from "./components/map";
import Planner from "./components/planner";
import Sidebar from "./components/sidebar";
import AIChat from "./components/ai-chat";
import { useParams } from "next/navigation";
import { Plan } from "@/types/plan";
import { getPlanById } from "@/api/plan/plan";
import { AxiosError } from "axios";
import toast from "react-hot-toast";
import { APIProvider } from "@vis.gl/react-google-maps";
import { ItineraryItem } from "@/types/itineraryItem";
import { ItineraryProvider } from "../../../../contexts/ItineraryContext";
import {
  MessageCircle,
  Map as MapIcon,
  ClipboardList,
  BotMessageSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const RightPanelControls = ({
  rightPanelView,
  setRightPanelView,
}: {
  rightPanelView: "map" | "planner";
  setRightPanelView: (v: "map" | "planner") => void;
}) => {
  return (
    <div className="absolute top-2 right-2 z-10 flex flex-col gap-2 items-end">
      <TooltipProvider delayDuration={100}>
        <div className="flex items-center rounded-lg border border-gray-300 bg-white/90 backdrop-blur-sm shadow-md overflow-hidden">
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={() => setRightPanelView("planner")}
                className={`flex items-center justify-center p-2.5 transition-all duration-200 ${
                  rightPanelView === "planner"
                    ? "bg-blue-600 text-white shadow-inner"
                    : "text-gray-600 hover:text-blue-600 hover:bg-blue-50"
                }`}
              >
                <ClipboardList className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              Planner
            </TooltipContent>
          </Tooltip>

          <div className="w-[1px] h-5 bg-gray-200" />

          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={() => setRightPanelView("map")}
                className={`flex items-center justify-center p-2.5 transition-all duration-200 ${
                  rightPanelView === "map"
                    ? "bg-blue-600 text-white shadow-inner"
                    : "text-gray-600 hover:text-blue-600 hover:bg-blue-50"
                }`}
              >
                <MapIcon className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              Map View
            </TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>
    </div>
  );
};

export default function PlanIdPage() {
  const params = useParams();
  const id = params.id as string;
  const [plan, setPlan] = useState<Plan | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  // AI Chat & right panel toggle
  const [isAIChatActive, setIsAIChatActive] = useState(false);
  const [rightPanelView, setRightPanelView] = useState<"map" | "planner">(
    "map",
  );
  useEffect(() => {
    if (!id) return;
    fetchPlan();
  }, [id]);
  const fetchPlan = async () => {
    try {
      const response = await getPlanById(id);
      setPlan(response);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Unexpected Error");
      } else {
        toast.error("Unexpected Error");
      }
    }
  };
  const [activeSection, setActiveSection] = useState("itinerary");
  const sectionRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isScrollingProgrammatically = useRef(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleSectionClick = useCallback((sectionId: string) => {
    setActiveSection(sectionId);
    // Disable scroll-based updates temporarily
    isScrollingProgrammatically.current = true;
    // Clear any existing timeout
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    const element = sectionRefs.current[sectionId];
    const container = scrollContainerRef.current;
    if (element && container) {
      const scrollPosition = element.offsetTop - 64 - 24 - 2 * 24; // HEADER_HEIGHT + SECTION_GAP + 2 * CONTAINER_PADDING
      // Listen for scrollend event to re-enable scroll tracking
      const handleScrollEnd = () => {
        isScrollingProgrammatically.current = false;
        container.removeEventListener("scrollend", handleScrollEnd);
      };
      container.addEventListener("scrollend", handleScrollEnd, { once: true });
      container.scrollTo({
        top: Math.max(0, scrollPosition),
        behavior: "smooth",
      });
      // Fallback timeout in case scrollend doesn't fire
      scrollTimeoutRef.current = setTimeout(() => {
        isScrollingProgrammatically.current = false;
        container.removeEventListener("scrollend", handleScrollEnd);
      }, 2000);
    }
  }, []);
  const handleSectionInView = useCallback((sectionId: string) => {
    // Only update if not currently scrolling programmatically
    if (!isScrollingProgrammatically.current) {
      setActiveSection(sectionId);
    }
  }, []);
  const handleItineraryItemUpdate = (newItem: ItineraryItem) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        itineraryDays: prev.itineraryDays?.map((d) => {
          // Check if this item already exists in this day (replace case)
          const existingIdx = (d.itineraryItems || []).findIndex(
            (i) => i.id === newItem.id,
          );
          if (existingIdx !== -1) {
            // Replace existing item
            const updatedItems = [...(d.itineraryItems || [])];
            updatedItems[existingIdx] = newItem;
            return { ...d, itineraryItems: updatedItems };
          }
          // Add new item to the matching day
          if (d.id === newItem.itineraryDayId) {
            return {
              ...d,
              itineraryItems: [...(d.itineraryItems || []), newItem],
            };
          }
          return d;
        }),
      };
    });
  };
  const handleToggleSidebarCollapse = useCallback(() => {
    setIsSidebarCollapsed((prev) => !prev);
  }, []);
  const handleOpenAIChat = useCallback(() => {
    setIsAIChatActive(true);
    setRightPanelView("map");
  }, []);
  const handleCloseAIChat = useCallback(() => {
    setIsAIChatActive(false);
  }, []);
  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);
  if (!plan) return null;
  return (
    <div className="w-full h-full flex p-4 gap-4">
      <APIProvider
        apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? ""}
        language="en"
      >
        <ItineraryProvider totalDays={plan.itineraryDays?.length ?? 0}>
          <div className="flex-shrink-0 h-full">
            <Sidebar
              activeSection={activeSection}
              onSectionClick={handleSectionClick}
              isCollapsed={isSidebarCollapsed}
              onToggleCollapse={handleToggleSidebarCollapse}
            />
          </div>
          {/* Center Panel */}
          <div className="flex-[4] h-full min-w-0">
            {isAIChatActive ? (
              <AIChat
                planName={plan.name}
                planStartDate={new Date(plan.startTime)}
                planEndDate={new Date(plan.endTime)}
                onClose={handleCloseAIChat}
                onPlanUpdated={(updatedPlan) => setPlan(updatedPlan)}
              />
            ) : (
              <Planner
                sectionRefs={sectionRefs}
                scrollContainerRef={scrollContainerRef}
                onSectionInView={handleSectionInView}
                plan={plan}
                setPlan={setPlan}
              />
            )}
          </div>
          {/* Right Panel */}
          <div
            id="right-panel-container"
            className="flex-[4] h-full min-w-0 relative"
          >
            {/* Toggle button Group - only visible when AI chat is active */}
            {isAIChatActive && (
              <RightPanelControls
                rightPanelView={rightPanelView}
                setRightPanelView={setRightPanelView}
              />
            )}
            {/* Right panel content */}
            {!isAIChatActive || rightPanelView === "map" ? (
              <GoogleMapIntegration
                plan={plan}
                onItineraryUpdate={handleItineraryItemUpdate}
              />
            ) : (
              <Planner
                sectionRefs={sectionRefs}
                scrollContainerRef={scrollContainerRef}
                onSectionInView={handleSectionInView}
                plan={plan}
                setPlan={setPlan}
              />
            )}
          </div>
        </ItineraryProvider>
      </APIProvider>
      {/* Floating AI Chat Button */}
      {!isAIChatActive && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleOpenAIChat}
                className="cursor-pointer fixed bottom-6 right-6 w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 transition-all duration-200 flex items-center justify-center z-40"
              >
                <BotMessageSquare className="w-6 h-6" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="left" className="text-xs">
              Plan with AI
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import GoogleMapIntegration from "./components/map";
import Planner from "./components/planner";
import Sidebar from "./components/sidebar";
import { useParams } from "next/navigation";
import { Plan } from "@/types/plan";
import { getPlanById } from "@/api/plan/plan";
import { AxiosError } from "axios";
import toast from "react-hot-toast";
import { APIProvider } from "@vis.gl/react-google-maps";
import { ItineraryItem } from "@/types/itineraryItem";
import { ItineraryProvider } from "../../../../contexts/ItineraryContext";

export default function PlanIdPage() {
  const params = useParams();
  const id = params.id as string;

  const [plan, setPlan] = useState<Plan | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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
        itineraryDays: prev.itineraryDays?.map((d) =>
          d.id === newItem.itineraryDayId
            ? {
                ...d,
                itineraryItems: [...(d.itineraryItems || []), newItem],
              }
            : d,
        ),
      };
    });
  };

  const handleToggleSidebarCollapse = useCallback(() => {
    setIsSidebarCollapsed((prev) => !prev);
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
      <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? ""}>
        <ItineraryProvider totalDays={plan.itineraryDays?.length ?? 0}>
          <div className="flex-shrink-0 h-full">
            <Sidebar
              activeSection={activeSection}
              onSectionClick={handleSectionClick}
              isCollapsed={isSidebarCollapsed}
              onToggleCollapse={handleToggleSidebarCollapse}
            />
          </div>

          <div className="flex-[5] h-full min-w-0">
            <Planner
              sectionRefs={sectionRefs}
              scrollContainerRef={scrollContainerRef}
              onSectionInView={handleSectionInView}
              plan={plan}
              setPlan={setPlan}
            />
          </div>

          <div className="flex-[5] h-full min-w-0">
            <GoogleMapIntegration
              plan={plan}
              onItineraryUpdate={handleItineraryItemUpdate}
            />
          </div>
        </ItineraryProvider>
      </APIProvider>
    </div>
  );
}

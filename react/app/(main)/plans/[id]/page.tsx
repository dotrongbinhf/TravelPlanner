"use client";

import { useEffect, useRef, useState } from "react";
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

  const handleSectionClick = (sectionId: string) => {
    setActiveSection(sectionId);

    const element = sectionRefs.current[sectionId];
    const container = scrollContainerRef.current;

    if (element && container) {
      const scrollPosition = element.offsetTop - 64 - 24 - 2 * 24; // HEADER_HEIGHT + SECTION_GAP + 2 * CONTAINER_PADDING

      container.scrollTo({
        top: Math.max(0, scrollPosition),
        behavior: "smooth",
      });
    }
  };

  const handleSectionInView = (sectionId: string) => {
    setActiveSection(sectionId);
  };

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

  if (!plan) return null;

  return (
    <div className="w-full flex p-4 gap-4">
      <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? ""}>
        <ItineraryProvider totalDays={plan.itineraryDays?.length ?? 0}>
          <div className="w-[200px] flex-shrink-0 h-full hidden lg:block">
            <Sidebar
              activeSection={activeSection}
              onSectionClick={handleSectionClick}
            />
          </div>

          <div className="flex-[4] h-full min-w-0">
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

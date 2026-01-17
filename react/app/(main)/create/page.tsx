"use client";

import { useRef, useState } from "react";
import Sidebar from "./components/sidebar";
import GoogleMapIntegration from "./components/map";
import Planner from "./components/planner";

export default function CreatePage() {
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

  return (
    <div className="w-full flex p-4 gap-4">
      <div className="flex-[2] flex-shrink-0 h-full">
        <Sidebar
          activeSection={activeSection}
          onSectionClick={handleSectionClick}
        />
      </div>

      <div className="flex-[5] h-full min-w-0`">
        <Planner
          sectionRefs={sectionRefs}
          scrollContainerRef={scrollContainerRef}
          onSectionInView={handleSectionInView}
        />
      </div>

      <div className="flex-[5] h-full min-w-0">
        <GoogleMapIntegration />
      </div>
    </div>
  );
}

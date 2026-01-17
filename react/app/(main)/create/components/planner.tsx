"use client";

import { useEffect, useCallback, useState, RefObject } from "react";
import Itinerary from "./sections/itinerary";
import Budget from "./sections/budget";
import PackingLists from "./sections/packing-lists";
import Teammates from "./sections/teammates";
import Notes from "./sections/notes";
import { sectionItems } from "./sidebar";

interface PlannerProps {
  readonly sectionRefs: RefObject<{
    [key: string]: HTMLDivElement | null;
  }>;
  readonly scrollContainerRef: RefObject<HTMLDivElement | null>;
  readonly onSectionInView: (sectionId: string) => void;
}

export default function Planner({
  sectionRefs,
  scrollContainerRef,
  onSectionInView,
}: PlannerProps) {
  const [spacerHeight, setSpacerHeight] = useState(0);
  const [notesContainerRef, setNotesContainerRef] =
    useState<HTMLDivElement | null>(null);

  // Calculate spacer height for Notes section
  useEffect(() => {
    const calculateSpacerHeight = () => {
      if (!notesContainerRef) return;

      const viewportHeight = window.innerHeight;
      const notesHeight = notesContainerRef.offsetHeight;

      // h-screen - header - outside container Padding * 2 - sectionGap - notesHeight
      const calculatedHeight = viewportHeight - 64 - 2 * 16 - 24 - notesHeight;

      setSpacerHeight(Math.max(0, calculatedHeight));
    };

    calculateSpacerHeight();

    // Recalculate on resize
    window.addEventListener("resize", calculateSpacerHeight);

    // Recalculate on changing content
    const resizeObserver = new ResizeObserver(calculateSpacerHeight);
    if (notesContainerRef) {
      resizeObserver.observe(notesContainerRef);
    }

    return () => {
      window.removeEventListener("resize", calculateSpacerHeight);
      resizeObserver.disconnect();
    };
  }, [notesContainerRef]);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const scrollTop = container.scrollTop;
    const offset = 64 + 16 + 24; // HEADER_HEIGHT + CONTAINER_PADDING + SECTION_GAP

    let activeSection = sectionItems[0].id;

    for (let i = sectionItems.length - 1; i >= 0; i--) {
      const element = sectionRefs.current[sectionItems[i].id];
      if (element) {
        const elementTop = element.offsetTop - offset;
        // SECTION_GAP + PADDING
        if (scrollTop >= elementTop - 24 - 24 - 1) {
          activeSection = sectionItems[i].id;
          break;
        }
      }
    }

    onSectionInView(activeSection);
  }, [onSectionInView, scrollContainerRef, sectionRefs]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    handleScroll();

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, [handleScroll, scrollContainerRef]);

  return (
    <div
      ref={scrollContainerRef}
      className="w-full h-full overflow-y-auto bg-white pr-4 custom-scrollbar"
    >
      <div className="flex flex-col gap-6">
        <div className="bg-white rounded-lg border-2 border-gray-200 p-6">
          <Itinerary
            ref={(el) => {
              sectionRefs.current["itinerary"] = el;
            }}
          />
        </div>

        <div className="bg-white rounded-lg border-2 border-gray-200 p-6">
          <Budget
            ref={(el) => {
              sectionRefs.current["budget"] = el;
            }}
          />
        </div>

        <div className="bg-white rounded-lg border-2 border-gray-200 p-6">
          <PackingLists
            ref={(el) => {
              sectionRefs.current["packing-lists"] = el;
            }}
          />
        </div>

        <div className="bg-white rounded-lg border-2 border-gray-200 p-6">
          <Teammates
            ref={(el) => {
              sectionRefs.current["teammates"] = el;
            }}
          />
        </div>

        <div
          ref={setNotesContainerRef}
          className="bg-white rounded-lg border-2 border-gray-200 p-6"
        >
          <Notes
            ref={(el) => {
              sectionRefs.current["notes"] = el;
            }}
          />
        </div>

        {/* Additional Spacer */}
        <div style={{ height: spacerHeight }} aria-hidden="true" />
      </div>
    </div>
  );
}

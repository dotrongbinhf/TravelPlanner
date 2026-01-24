"use client";

import {
  useEffect,
  useCallback,
  useState,
  RefObject,
  SetStateAction,
  Dispatch,
} from "react";
import Overview from "./sections/overview";
import Itinerary from "./sections/itinerary";
import Budget from "./sections/budget";
import PackingLists from "./sections/packing-lists";
import Teammates from "./sections/teammates";
import Notes from "./sections/notes";
import { sectionItems } from "./sidebar";
import { Plan } from "@/types/plan";
import { Note } from "@/types/note";
import { PackingList } from "@/types/packingList";
import { ExpenseItem } from "@/types/budget";

interface PlannerProps {
  readonly sectionRefs: RefObject<{
    [key: string]: HTMLDivElement | null;
  }>;
  readonly scrollContainerRef: RefObject<HTMLDivElement | null>;
  readonly onSectionInView: (sectionId: string) => void;
  readonly plan: Plan;
  readonly setPlan: Dispatch<SetStateAction<Plan | null>>;
}

export default function Planner({
  sectionRefs,
  scrollContainerRef,
  onSectionInView,
  plan,
  setPlan,
}: PlannerProps) {
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

  const updateNotes = (notes: Note[]) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        notes,
      };
    });
  };

  const updatePackingLists = (packingLists: PackingList[]) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        packingLists,
      };
    });
  };

  const updateExpenseItems = (expenseItems: ExpenseItem[]) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        expenseItems,
      };
    });
  };

  const updateBudgetAndCurrencyCode = (
    budget: number,
    currencyCode: string,
  ) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        budget,
        currencyCode,
      };
    });
  };

  const updatePlanName = (name: string) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        name,
      };
    });
  };

  const updatePlanCoverImageUrl = (coverImageUrl: string) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        coverImageUrl,
      };
    });
  };

  const updatePlanDuration = (startTime: Date, endTime: Date) => {
    setPlan((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        startTime,
        endTime,
      };
    });
  };

  return (
    <div
      ref={scrollContainerRef}
      className="w-full h-full overflow-y-auto pr-4 custom-scrollbar"
    >
      <div className="flex flex-col gap-6">
        <div className="rounded-lg border-2 border-gray-200 p-6">
          <Overview
            planId={plan.id}
            ref={(el) => {
              sectionRefs.current["overview"] = el;
            }}
            name={plan.name}
            coverImageUrl={plan.coverImageUrl}
            startTime={new Date(plan.startTime)}
            endTime={new Date(plan.endTime)}
            budget={plan.budget}
            currencyCode={plan.currencyCode}
            updatePlanName={updatePlanName}
            updatePlanCoverImageUrl={updatePlanCoverImageUrl}
          />
        </div>

        <div className="rounded-lg border-2 border-gray-200 p-6">
          <Itinerary
            ref={(el) => {
              sectionRefs.current["itinerary"] = el;
            }}
          />
        </div>

        <div className="rounded-lg border-2 border-gray-200 p-6">
          <Budget
            ref={(el) => {
              sectionRefs.current["budget"] = el;
            }}
            planId={plan.id}
            totalBudget={plan.budget}
            currencyCode={plan.currencyCode}
            expenseItems={plan.expenseItems}
            updateExpenseItems={updateExpenseItems}
            updateBudgetAndCurrencyCode={updateBudgetAndCurrencyCode}
          />
        </div>

        <div className="rounded-lg border-2 border-gray-200 p-6">
          <PackingLists
            ref={(el) => {
              sectionRefs.current["packing-lists"] = el;
            }}
            planId={plan.id}
            packingLists={plan.packingLists}
            updatePackingLists={updatePackingLists}
          />
        </div>

        <div className="rounded-lg border-2 border-gray-200 p-6">
          <Teammates
            ref={(el) => {
              sectionRefs.current["teammates"] = el;
            }}
          />
        </div>

        <div className="rounded-lg border-2 border-gray-200 p-6">
          <Notes
            ref={(el) => {
              sectionRefs.current["notes"] = el;
            }}
            planId={plan.id}
            notes={plan.notes}
            updateNotes={updateNotes}
          />
        </div>

        {/* Additional Spacer */}
        <div style={{ height: "100vh" }} aria-hidden="true" />
      </div>
    </div>
  );
}

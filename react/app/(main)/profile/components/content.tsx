"use client";

import {
  useEffect,
  useCallback,
  RefObject,
  Dispatch,
  SetStateAction,
} from "react";
import { profileSectionItems } from "./sidebar";
import { User } from "@/types/user";
import ChangePassword from "./sections/change-password";
import UserInformation from "./sections/user-information";

interface ProfileContentProps {
  readonly sectionRefs: RefObject<{
    [key: string]: HTMLDivElement | null;
  }>;
  readonly scrollContainerRef: RefObject<HTMLDivElement | null>;
  readonly onSectionInView: (sectionId: string) => void;
  readonly user: User;
  readonly setUser: Dispatch<SetStateAction<User | null>>;
}

export default function ProfileContent({
  sectionRefs,
  scrollContainerRef,
  onSectionInView,
  user,
  setUser,
}: ProfileContentProps) {
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const scrollTop = container.scrollTop;
    const offset = 64 + 16 + 24; // HEADER_HEIGHT + CONTAINER_PADDING + SECTION_GAP

    let activeSection = profileSectionItems[0].id;

    for (let i = profileSectionItems.length - 1; i >= 0; i--) {
      const element = sectionRefs.current[profileSectionItems[i].id];
      if (element) {
        const elementTop = element.offsetTop - offset;
        if (scrollTop >= elementTop - 24 - 24 - 1) {
          activeSection = profileSectionItems[i].id;
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

  const updateUser = (updatedUser: User) => {
    setUser(updatedUser);
  };

  console.log(user);

  return (
    <div
      ref={scrollContainerRef}
      className="w-full h-full overflow-y-auto pr-4 custom-scrollbar"
    >
      <div className="flex flex-col gap-6">
        <div className="rounded-lg border-2 border-gray-200 p-6">
          <UserInformation
            ref={(el: HTMLDivElement | null) => {
              sectionRefs.current["user-information"] = el;
            }}
            user={user}
            updateUser={updateUser}
          />
        </div>

        <div className="rounded-lg border-2 border-gray-200 p-6">
          <ChangePassword
            ref={(el: HTMLDivElement | null) => {
              sectionRefs.current["change-password"] = el;
            }}
          />
        </div>

        {/* Additional Spacer */}
        <div style={{ height: "100vh" }} aria-hidden="true" />
      </div>
    </div>
  );
}

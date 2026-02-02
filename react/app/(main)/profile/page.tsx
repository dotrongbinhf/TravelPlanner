"use client";

import { useEffect, useRef, useState } from "react";
import ProfileSidebar from "./components/sidebar";
import ProfileContent from "./components/content";
import { getUserProfile } from "@/api/user/user";
import { AxiosError } from "axios";
import toast from "react-hot-toast";
import { useAppContext } from "@/contexts/AppContext";

export default function ProfilePage() {
  const { user, setUser } = useAppContext();
  const [activeSection, setActiveSection] = useState("user-information");
  const sectionRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchUserProfile();
  }, []);

  const fetchUserProfile = async () => {
    if (user) return; // Skip if user is already loaded from context
    try {
      const response = await getUserProfile();
      setUser(response);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to load profile");
      } else {
        toast.error("Failed to load profile");
      }
    }
  };

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

  if (!user) return null;

  return (
    <div className="w-full flex p-4 gap-4">
      <div className="w-[200px] flex-shrink-0 h-full hidden lg:block">
        <ProfileSidebar
          activeSection={activeSection}
          onSectionClick={handleSectionClick}
        />
      </div>

      <div className="flex-[10] h-full min-w-0">
        <ProfileContent
          sectionRefs={sectionRefs}
          scrollContainerRef={scrollContainerRef}
          onSectionInView={handleSectionInView}
          user={user}
          setUser={setUser}
        />
      </div>
    </div>
  );
}

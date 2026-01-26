"use client";

import { User, Lock } from "lucide-react";

interface ProfileSidebarProps {
  activeSection: string;
  onSectionClick: (sectionId: string) => void;
}

export const profileSectionItems = [
  { id: "user-information", title: "User Information", icon: User },
  { id: "change-password", title: "Change Password", icon: Lock },
];

export default function ProfileSidebar({
  activeSection,
  onSectionClick,
}: ProfileSidebarProps) {
  return (
    <div className="w-full h-full bg-white">
      <nav className="flex flex-col gap-1">
        {profileSectionItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onSectionClick(item.id)}
              className={`cursor-pointer flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-colors duration-200
                ${
                  isActive
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }
              `}
            >
              <Icon
                size={20}
                className={isActive ? "text-blue-700" : "text-gray-500"}
              />
              <span className="text-sm">{item.title}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}

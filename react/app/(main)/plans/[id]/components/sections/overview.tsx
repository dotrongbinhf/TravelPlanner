"use client";

import { forwardRef, useMemo } from "react";
import { Calendar, Users, Wallet, MapPin } from "lucide-react";
import Image from "next/image";

interface OverviewProps {
  name: string;
  coverImageUrl?: string;
  startTime: string; // ISO date string: "2026-01-25T17:00:00+00:00"
  endTime: string;
  // totalMembers: number;
  budget: number;
  currencyCode: string;
  // totalDestinations: number;
}

const Overview = forwardRef<HTMLDivElement, OverviewProps>((props, ref) => {
  const startDate = useMemo(
    () => (props.startTime ? new Date(props.startTime) : null),
    [props.startTime],
  );
  const endDate = useMemo(
    () => (props.endTime ? new Date(props.endTime) : null),
    [props.endTime],
  );

  const planData = {
    name: props.name,
    coverImage: props.coverImageUrl || "/default-plan-cover.jpg",
    startTime: startDate,
    endTime: endDate,
    // totalMembers: props.totalMembers,
    budget: props.budget,
    currencyCode: props.currencyCode,
    // totalDestinations: props.totalDestinations,
  };

  const formatDate = (date: Date | null) => {
    if (!date) return "";
    return date.toLocaleDateString("en-US", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const calculateDays = (start: Date | null, end: Date | null) => {
    if (!start || !end) return 0;
    const diffTime = Math.abs(end.getTime() - start.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays + 1;
  };

  return (
    <div ref={ref}>
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Overview</h2>

      {/* Cover Image */}
      <div className="relative w-full h-48 md:h-64 rounded-lg overflow-hidden mb-6 bg-gray-200">
        <Image
          src={planData.coverImage}
          alt={planData.name}
          fill
          className="object-cover"
          priority
          onError={(e) => {
            // Fallback for missing image
            const target = e.target as HTMLImageElement;
            target.style.display = "none";
          }}
        />
        {/* Fallback gradient background */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-400 to-purple-500 -z-10" />
      </div>

      {/* Plan Name */}
      <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-6">
        {planData.name}
      </h1>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Date */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Calendar size={18} className="text-blue-600" />
            <span className="text-sm font-medium text-gray-600">Duration</span>
          </div>
          <p className="text-sm font-semibold text-gray-900">
            {formatDate(planData.startTime)}
          </p>
          <p className="text-sm text-gray-500">to</p>
          <p className="text-sm font-semibold text-gray-900">
            {formatDate(planData.endTime)}
          </p>
          <p className="text-xs text-blue-600 mt-1">
            ({calculateDays(planData.startTime, planData.endTime)} days)
          </p>
        </div>

        {/* Members */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users size={18} className="text-green-600" />
            <span className="text-sm font-medium text-gray-600">Travelers</span>
          </div>
          <p className="text-2xl font-bold text-gray-900">
            {/* {planData.totalMembers} */}1
          </p>
          <p className="text-xs text-gray-500">
            {/* {planData.totalMembers === 1 ? "person" : "people"} */}1 people
          </p>
        </div>

        {/* Budget */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Wallet size={18} className="text-amber-600" />
            <span className="text-sm font-medium text-gray-600">Budget</span>
          </div>
          <p className="text-2xl font-bold text-gray-900">
            ${planData.budget.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500">{planData.currencyCode}</p>
        </div>

        {/* Destinations */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <MapPin size={18} className="text-red-600" />
            <span className="text-sm font-medium text-gray-600">Places</span>
          </div>
          <p className="text-2xl font-bold text-gray-900">{15}</p>
          <p className="text-xs text-gray-500">
            {/* {planData.totalDestinations === 1 ? "destination" : "destinations"} */}
            15 destinations
          </p>
        </div>
      </div>
    </div>
  );
});

Overview.displayName = "Overview";

export default Overview;

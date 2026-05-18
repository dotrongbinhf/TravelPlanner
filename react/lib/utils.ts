import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getCategoryFallback(category?: string | null): string {
  if (!category) return "/images/plans/alternative-place.jpg";
  const cat = category.toLowerCase();
  if (
    cat.includes("hotel") ||
    cat.includes("lodging") ||
    cat.includes("stay") ||
    cat.includes("motel") ||
    cat.includes("accommodation")
  ) {
    return "/images/plans/alternative-hotel.jpg";
  }
  if (
    cat.includes("restaurant") ||
    cat.includes("food") ||
    cat.includes("meal") ||
    cat.includes("cafe") ||
    cat.includes("dining") ||
    cat.includes("bar")
  ) {
    return "/images/plans/alternative-restaurant.jpg";
  }
  if (
    cat.includes("attraction") ||
    cat.includes("park") ||
    cat.includes("museum") ||
    cat.includes("sight") ||
    cat.includes("point_of_interest") ||
    cat.includes("tourist")
  ) {
    return "/images/plans/alternative-place.jpg";
  }
  return "/images/plans/alternative-place.jpg";
}

export function getPlaceImage(
  url?: string | null,
  fallback: string = "/images/plans/alternative-place.jpg",
): string {
  if (
    !url ||
    url.trim() === "" ||
    url === "https://placehold.co/600x400?text=No+Image"
  ) {
    return fallback;
  }
  return url;
}

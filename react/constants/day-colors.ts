// Color palette for different days in the itinerary
export const DAY_COLORS = [
  "#039BE5",
  "#E67C73",
  "#33B679",
  "#F59E0B",
  "#3F51B5",
  "#7986CB",
  "#14B8A6",
  "#8E24AA",
  "#616161",
  "#84CC16",
];

export function getDayColor(dayIndex: number): string {
  return DAY_COLORS[dayIndex % DAY_COLORS.length];
}

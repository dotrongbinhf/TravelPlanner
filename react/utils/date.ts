import { format } from "date-fns";

export const formatDateRange = (start: Date, end: Date) => {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (startDate.getFullYear() === endDate.getFullYear()) {
    return `${format(startDate, "MMM d")} - ${format(endDate, "MMM d, yyyy")}`;
  }
  return `${format(startDate, "MMM d, yyyy")} - ${format(endDate, "MMM d, yyyy")}`;
};

import { ExpenseItem } from "./budget";
import { ItineraryDay } from "./itineraryDay";
import { Note } from "./note";
import { PackingList } from "./packingList";
import { Collaborator } from "./participant";

export type Plan = {
  id: string;
  ownerId: string;
  name: string;
  coverImageUrl: string | undefined;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;

  // Owner info
  ownerName?: string;
  ownerUsername?: string;
  ownerAvatarUrl?: string;

  collaboratorId?: string;
  notes?: Note[];
  packingLists?: PackingList[];
  itineraryDays?: ItineraryDay[];
  expenseItems?: ExpenseItem[];
  collaborators?: Collaborator[];
  lastSyncGoogleCalendarAt?: string;
  createdAt?: string;
};

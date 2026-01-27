import { ExpenseItem } from "./budget";
import { Note } from "./note";
import { PackingList } from "./packingList";
import { Participant } from "./participant";

export type Plan = {
  id: string;
  ownerId: string;
  name: string;
  coverImageUrl: string | undefined;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;

  participantId?: string;
  notes?: Note[];
  packingLists?: PackingList[];
  expenseItems?: ExpenseItem[];
  participants?: Participant[];
};

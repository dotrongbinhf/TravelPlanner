import { Note } from "./note";
import { PackingList } from "./packingList";

export type Plan = {
  id: string;
  ownerId: string;
  name: string;
  coverImageUrl: string | undefined;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;
  notes: Note[];
  packingLists: PackingList[];
};

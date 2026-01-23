import { PackingItem } from "./packingItem";

export type PackingList = {
  id: string;
  planId: string;
  name: string;
  packingItems: PackingItem[];
};

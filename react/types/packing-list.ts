export type PackingList = {
  id: string;
  planId: string;
  name: string;
  items: PackingItem[];
};

export type PackingItem = {
  id: string;
  name: string;
  checked: boolean;
};

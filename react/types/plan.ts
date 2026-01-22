export type Plan = {
  id: string;
  ownerId: string;
  name: string;
  coverImageUrl: string | undefined;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;
};

export type CreatePlanRequest = {
  name: string;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;
};

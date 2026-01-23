export type CreatePlanRequest = {
  name: string;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;
};

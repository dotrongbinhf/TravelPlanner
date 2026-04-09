import API from "@/utils/api";

const APP_CONFIG_URL = "/api/GoogleCalendar";

export type GoogleAuthStatusResponse = {
  isConnected: boolean;
  email?: string;
  avatarUrl?: string;
};

export type SyncGoogleCalendarResponse = {
  syncedAt: string;
  createdCount: number;
  updatedCount: number;
  deletedCount: number;
  eventMappings: { itineraryItemId: string; googleCalendarEventId: string }[];
};

export const exchangeGoogleCode = async (code: string) => {
  const response = await API.post<GoogleAuthStatusResponse>(
    `${APP_CONFIG_URL}/exchange-code`,
    { code },
  );
  return response.data;
};

export const getGoogleAuthStatus = async () => {
  const response = await API.get<GoogleAuthStatusResponse>(
    `${APP_CONFIG_URL}/auth-status`,
  );
  return response.data;
};

export const syncGoogleCalendar = async (planId: string, timeZoneOffsetMinutes: number, timeZone: string) => {
  const response = await API.post<SyncGoogleCalendarResponse>(
    `${APP_CONFIG_URL}/sync/${planId}?timeZoneOffsetMinutes=${timeZoneOffsetMinutes}&timeZone=${encodeURIComponent(timeZone)}`,
  );
  return response.data;
};

export const disconnectGoogle = async () => {
  const response = await API.post<GoogleAuthStatusResponse>(
    `${APP_CONFIG_URL}/disconnect`,
  );
  return response.data;
};

export const unsyncGoogleCalendar = async (planId: string) => {
  const response = await API.post(
    `${APP_CONFIG_URL}/unsync/${planId}`,
  );
  return response.data;
};

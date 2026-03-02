"use client";

import { useState, useCallback, useEffect } from "react";
import {
  exchangeGoogleCode,
  getGoogleAuthStatus,
  syncGoogleCalendar,
  disconnectGoogle,
  type SyncGoogleCalendarResponse,
} from "@/api/googleCalendar/googleCalendar";
import toast from "react-hot-toast";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
const GOOGLE_REDIRECT_URI =
  typeof window !== "undefined"
    ? `${window.location.origin}/auth/google/callback`
    : "";
const GOOGLE_SCOPE =
  "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile";

export function useGoogleCalendar() {
  const [isConnected, setIsConnected] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [googleEmail, setGoogleEmail] = useState<string | undefined>();
  const [googleAvatarUrl, setGoogleAvatarUrl] = useState<string | undefined>();

  // Check auth status on mount
  const checkAuthStatus = useCallback(async () => {
    try {
      setIsCheckingAuth(true);
      const status = await getGoogleAuthStatus();
      setIsConnected(status.isConnected);
      setGoogleEmail(status.email);
      setGoogleAvatarUrl(status.avatarUrl);
    } catch {
      setIsConnected(false);
    } finally {
      setIsCheckingAuth(false);
    }
  }, []);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  // Open Google OAuth popup
  const connectGoogle = useCallback((): Promise<void> => {
    return new Promise((resolve, reject) => {
      // Generate random state for CSRF protection
      const state = crypto.randomUUID();
      sessionStorage.setItem("google_oauth_state", state);

      const params = new URLSearchParams({
        client_id: GOOGLE_CLIENT_ID ?? "",
        redirect_uri: GOOGLE_REDIRECT_URI,
        response_type: "code",
        scope: GOOGLE_SCOPE,
        access_type: "offline",
        prompt: "consent",
        state,
      });

      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;

      // Open popup
      const popup = window.open(
        authUrl,
        "google-auth",
        "width=500,height=600,left=200,top=100",
      );

      if (!popup) {
        toast.error("Popup blocked. Please allow popups for this site.");
        reject(new Error("Popup blocked"));
        return;
      }

      // Listen for message from callback page
      const handleMessage = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;
        if (event.data?.type !== "google-auth-callback") return;

        window.removeEventListener("message", handleMessage);

        if (event.data.error) {
          toast.error(`Google auth failed: ${event.data.error}`);
          reject(new Error(event.data.error));
          return;
        }

        if (event.data.code) {
          try {
            const result = await exchangeGoogleCode(event.data.code);
            setIsConnected(true);
            setGoogleEmail(result.email);
            setGoogleAvatarUrl(result.avatarUrl);
            toast.success("Connected to Google Calendar!");
            resolve();
          } catch {
            toast.error("Failed to connect Google Calendar");
            reject(new Error("Exchange failed"));
          }
        }
      };

      window.addEventListener("message", handleMessage);

      // Cleanup if popup is closed without completing
      const pollTimer = setInterval(() => {
        if (popup.closed) {
          clearInterval(pollTimer);
          window.removeEventListener("message", handleMessage);
        }
      }, 500);
    });
  }, []);

  // Sync itinerary to Google Calendar
  const syncCalendar = useCallback(
    async (planId: string): Promise<SyncGoogleCalendarResponse | null> => {
      setIsSyncing(true);
      try {
        const result = await syncGoogleCalendar(planId);
        const totalActions =
          result.createdCount + result.updatedCount + result.deletedCount;
        toast.success(
          `Synced! ${result.createdCount} created, ${result.updatedCount} updated, ${result.deletedCount} deleted (${totalActions} total)`,
        );
        return result;
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Sync failed";
        if (message.includes("expired") || message.includes("reconnect")) {
          setIsConnected(false);
          setGoogleEmail(undefined);
          setGoogleAvatarUrl(undefined);
          toast.error("Google Calendar session expired. Please reconnect.");
        } else {
          toast.error(`Sync failed: ${message}`);
        }
        return null;
      } finally {
        setIsSyncing(false);
      }
    },
    [],
  );

  const disconnectAccount = useCallback(async () => {
    try {
      await disconnectGoogle();
      setIsConnected(false);
      setGoogleEmail(undefined);
      setGoogleAvatarUrl(undefined);
      toast.success("Disconnected from Google Calendar");
    } catch {
      toast.error("Failed to disconnect from Google Calendar");
    }
  }, []);

  return {
    isConnected,
    isSyncing,
    isCheckingAuth,
    googleEmail,
    googleAvatarUrl,
    connectGoogle,
    syncCalendar,
    checkAuthStatus,
    disconnectAccount,
  };
}

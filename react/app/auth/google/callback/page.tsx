"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, Suspense } from "react";

function CallbackContent() {
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    // Verify state matches what we stored
    const savedState = sessionStorage.getItem("google_oauth_state");

    if (state && savedState && state === savedState) {
      sessionStorage.removeItem("google_oauth_state");

      // Send code to parent window
      if (window.opener) {
        window.opener.postMessage(
          { type: "google-auth-callback", code },
          window.location.origin,
        );
      }
    } else {
      // State mismatch - potential CSRF
      if (window.opener) {
        window.opener.postMessage(
          { type: "google-auth-callback", error: "State mismatch" },
          window.location.origin,
        );
      }
    }

    // Close popup after a short delay
    setTimeout(() => window.close(), 500);
  }, [searchParams]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-600">Connecting to Google Calendar...</p>
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}

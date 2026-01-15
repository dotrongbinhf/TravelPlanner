"use client";

import Header from "@/components/Header";
import { TokenStorage } from "@/utils/tokenStorage";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const accessToken = TokenStorage.getAccessToken();

  useEffect(() => {
    if (!accessToken) {
      router.replace("/login");
    }
  }, []);

  if (!accessToken) {
    return null;
  }

  return (
    <div className="flex flex-col h-full w-full">
      <Header />
      <main className="flex-1 flex justify-center">{children}</main>
    </div>
  );
}

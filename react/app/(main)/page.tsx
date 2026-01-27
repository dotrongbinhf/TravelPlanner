"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.push("/plans");
  }, []);

  return (
    <div className="h-full w-full flex justify-center items-center">
      <h1>Welcome to TravelPlanner!</h1>
    </div>
  );
}

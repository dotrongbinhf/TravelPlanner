"use client";

import { getAllUsers } from "@/api/auth/auth";
import { useEffect } from "react";

export default function Home() {
  useEffect(() => {
    getAllUsers().then((users) => {
      console.log("All Users:", users);
    });
  }, []);

  return (
    <div className="h-full w-full flex justify-center items-center">
      <h1>Welcome to TravelPlanner!</h1>
    </div>
  );
}

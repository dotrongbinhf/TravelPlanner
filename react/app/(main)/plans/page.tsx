"use client";

import { getAllPlans } from "@/api/plan/plan";
import { Plan } from "@/types/plan";
import { AxiosError } from "axios";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

export default function MyPlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  useEffect(() => {
    fetchAllPlans();
  }, []);

  const fetchAllPlans = async () => {
    try {
      const response = await getAllPlans();
      setPlans(response);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Unexpected Error");
      } else {
        toast.error("Unexpected Error");
      }
    }
  };
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">My Plans</h1>
      <ul className="space-y-4">
        {plans.map((plan) => (
          <li key={plan.id} className="p-4 border rounded-lg shadow-sm">
            <h2 className="text-xl font-semibold">{plan.name}</h2>
            <a href={`plans/${plan.id}`}>View Details</a>
          </li>
        ))}
      </ul>
    </div>
  );
}

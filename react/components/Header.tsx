"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Settings, User, Plus } from "lucide-react";
import { useState, useEffect } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";
import { CustomDialog } from "@/components/custom-dialog";
import { DateRangePicker } from "@/components/date-range-picker";
import { CurrencyInput } from "@/components/currency-input";
import { logout } from "@/api/auth/auth";
import { TokenStorage } from "@/utils/tokenStorage";
import toast from "react-hot-toast";
import { NAV_ITEMS } from "@/constants/routes";
import { cn } from "@/lib/utils";
import { AxiosError } from "axios";
import { createPlan } from "@/api/plan/plan";
import { CreatePlanRequest } from "@/api/plan/types";
import { useAppContext } from "@/contexts/AppContext";
import { getUserProfile } from "@/api/user/user";
import { getInitials, getResizedImageUrl } from "@/utils/image";

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const { user, setUser } = useAppContext();

  // Form state
  const [planName, setPlanName] = useState("");
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("USD");

  // Fetch user profile on mount if not already loaded
  useEffect(() => {
    const fetchUserProfile = async () => {
      if (!user) {
        try {
          const response = await getUserProfile();
          setUser(response);
        } catch (error) {
          console.error("Failed to fetch user profile:", error);
        }
      }
    };
    fetchUserProfile();
  }, [user]);

  const isActive = (href: string) => pathname.includes(href);

  const handleLogout = async () => {
    try {
      await logout();
      TokenStorage.removeAccessToken();
      router.push("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  const handleCreatePlan = async () => {
    // Logic để tạo plan mới
    const newPlan = {
      name: planName,
      startTime: startDate,
      endTime: endDate,
      budget: parseFloat(budget),
      currencyCode: currency,
    } as CreatePlanRequest;
    // You can call your API here to create the plan using newPlan object
    try {
      const response = await createPlan(newPlan);
      toast.success("Plan Created Successfully!");
      router.replace("/plans/" + response.id);
    } catch (error) {
      console.error("Create plan failed:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Unexpected Error");
      } else {
        toast.error("Unexpected Create Plan Error");
      }
    }

    // Reset form
    setPlanName("");
    setStartDate(null);
    setEndDate(null);
    setBudget("");
    setCurrency("USD");
  };

  const handleDialogClose = (open: boolean) => {
    setIsDialogOpen(open);
    if (!open) {
      // Reset form when dialog closes
      setPlanName("");
      setStartDate(null);
      setEndDate(null);
      setBudget("");
      setCurrency("USD");
    }
  };

  return (
    <header className="w-full bg-white shadow-sm border-b border-gray-200">
      <div className="w-full mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex gap-8 items-center">
            {/* Logo & Brand Name */}
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">T</span>
              </div>
              <span className="text-xl font-bold text-gray-800">
                Travel<span className="text-blue-600">Planner</span>
              </span>
            </Link>

            {/* Navigation Menu */}
            <NavigationMenu className="flex">
              <NavigationMenuList>
                {NAV_ITEMS.map((item) => (
                  <NavigationMenuItem key={item.href}>
                    <Link href={item.href} legacyBehavior passHref>
                      <NavigationMenuLink
                        className={cn(
                          navigationMenuTriggerStyle(),
                          isActive(item.href)
                            ? "!bg-blue-50 !text-blue-700"
                            : "",
                        )}
                        active={isActive(item.href)}
                      >
                        {item.label}
                      </NavigationMenuLink>
                    </Link>
                  </NavigationMenuItem>
                ))}
              </NavigationMenuList>
            </NavigationMenu>
          </div>

          <div className="flex items-center gap-2">
            {/* New Plan Button */}
            <button
              onClick={() => setIsDialogOpen(true)}
              className="cursor-pointer bg-blue-500 hover:bg-blue-600 text-white font-semibold text-sm px-3 py-3 rounded-lg flex items-center gap-2 transition-colors duration-200"
            >
              <Plus className="w-4 h-4" strokeWidth={3} />
              Create New Plan
            </button>

            {/* User Profile Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="cursor-pointer flex items-center gap-3 px-2 transition-all duration-200 outline-none">
                  <Avatar className="h-10 w-10 border-2 border-gray-200">
                    <AvatarImage
                      src={getResizedImageUrl(user?.avatarUrl ?? "", 256, 256)}
                      alt={user?.name || user?.username}
                      className="object-cover"
                    />
                    <AvatarFallback className="bg-blue-400 text-white">
                      {getInitials(user?.name, user?.username)}
                    </AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuItem
                  className="cursor-text focus:bg-transparent focus:text-inherit"
                  onSelect={(e) => e.preventDefault()}
                >
                  <div className="flex items-center gap-3 pointer-events-none">
                    <Avatar className="h-10 w-10 border-2 border-gray-200">
                      <AvatarImage
                        src={getResizedImageUrl(
                          user?.avatarUrl ?? "",
                          256,
                          256,
                        )}
                        alt={user?.name || user?.username}
                        className="object-cover"
                      />
                      <AvatarFallback className="bg-blue-400 text-white">
                        {getInitials(user?.name, user?.username)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col leading-tight pointer-events-auto">
                      <span className="text-sm font-semibold text-gray-900 select-text">
                        {user?.username}
                      </span>
                      <span className="text-xs text-gray-500 select-text">
                        {user?.name ?? ""}
                      </span>
                    </div>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link
                    href="/profile"
                    className="flex items-center gap-3 cursor-pointer"
                  >
                    <User className="w-4 h-4" />
                    <span>Profile</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link
                    href="/settings"
                    className="flex items-center gap-3 cursor-pointer"
                  >
                    <Settings className="w-4 h-4" />
                    <span>Settings</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={handleLogout}
                  className="text-red-600 focus:text-red-600 focus:bg-red-50 cursor-pointer flex items-center gap-3"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Logout</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* New Plan Dialog */}
      <CustomDialog
        open={isDialogOpen}
        onOpenChange={handleDialogClose}
        title="Create New Plan"
        description="Fill in the details to create your new travel plan"
        cancelLabel="Cancel"
        confirmLabel="Create"
        onConfirm={handleCreatePlan}
        isDisabled={
          planName.trim() === "" || !startDate || !endDate || budget === ""
        }
      >
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700">
              Plan Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              placeholder="E.g. Hanoi Friendship"
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700">
              Travel Dates
              {/* <span className="text-red-500">*</span> */}
            </label>
            <div className="mt-1">
              <DateRangePicker
                startDate={startDate}
                endDate={endDate}
                onChange={(start, end) => {
                  setStartDate(start);
                  setEndDate(end);
                }}
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700">Budget</label>
            <div className="mt-1">
              <CurrencyInput
                value={budget}
                currency={currency}
                onValueChange={setBudget}
                onCurrencyChange={setCurrency}
              />
            </div>
          </div>
        </div>
      </CustomDialog>
    </header>
  );
}

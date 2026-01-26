"use client";

import { createContext, useContext, useState } from "react";
import { User } from "@/types/user";

interface AppContextProps {
  accessToken: string | null;
  setAccessToken: (token: string | null) => void;
  user: User | null;
  setUser: (user: User | null) => void;
}

const AppContext = createContext<AppContextProps | undefined>(undefined);

export const AppContextProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  return (
    <AppContext.Provider value={{ accessToken, setAccessToken, user, setUser }}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppContextProvider");
  }
  return context;
};

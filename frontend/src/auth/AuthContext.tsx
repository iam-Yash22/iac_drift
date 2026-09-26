import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { getCurrentUser, login as loginRequest } from "@/api/auth";
import type { AuthTokens, LoginCredentials, User } from "@/api/auth";

type AuthContextValue = {
  user: User | null;
  role: "admin" | "regular" | null;
  isLoading: boolean;
  login: (credentials: LoginCredentials, remember?: boolean) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function storeAccessToken(token: string, remember: boolean) {
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem("access_token", token);
  const otherStorage = remember ? sessionStorage : localStorage;
  otherStorage.removeItem("access_token");
}

function readAccessToken() {
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(readAccessToken()));

  useEffect(() => {
    const token = readAccessToken();

    if (!token || window.location.pathname === "/signin") {
      setIsLoading(false);
      return;
    }

    getCurrentUser()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("access_token");
        sessionStorage.removeItem("access_token");
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (credentials: LoginCredentials, remember = true) => {
    const tokens: AuthTokens = await loginRequest(credentials);
    storeAccessToken(tokens.access_token, remember);

    try {
      setUser(await getCurrentUser());
    } catch (error) {
      logout();
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    sessionStorage.removeItem("access_token");
    setUser(null);
  };

  const role = user?.role === "admin" ? "admin" : user ? "regular" : null;

  return (
    <AuthContext.Provider value={{ user, role, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

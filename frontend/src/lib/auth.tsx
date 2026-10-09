"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { type Role, type User } from "@/lib/types";

export const HOME: Record<Role, string> = {
  doctor: "/doctor/",
  nurse: "/nurse/",
  patient: "/patient/",
  family: "/patient/",
  dietitian: "/dietitian/",
  org_admin: "/manage/",
  auditor: "/login/",
  sys_admin: "/login/",
};

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // The server says who this is; nothing about the role is kept or trusted on the client.
    const restore = api.hasSession()
      ? api.get<User>("/auth/me/").catch(() => null)
      : Promise.resolve(null);
    restore.then((me) => {
      setUser(me);
      setReady(true);
    });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const me = await api.login(username, password);
    setUser(me);
    return me;
  }, []);
  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);
  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside AuthProvider");
  return state;
}

/**
 * Sends signed-out users to /login and users of another role to their own home. This is
 * navigation convenience only: every API call is authorized again on the server.
 */
export function useRole(...allowed: Role[]): User | null {
  const { user, ready } = useAuth();
  const router = useRouter();
  const ok = user !== null && allowed.includes(user.role);
  useEffect(() => {
    if (!ready || ok) return;
    router.replace(user ? HOME[user.role] : "/login/");
  }, [ready, ok, user, router]);
  return ok ? user : null;
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { HOME, useAuth } from "@/lib/auth";

/** Sends each user to the dashboard for their role. */
export default function Index() {
  const { user, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready) router.replace(user ? HOME[user.role] : "/login/");
  }, [ready, user, router]);
  return <p className="p-6 text-sm text-slate-500">Loading…</p>;
}

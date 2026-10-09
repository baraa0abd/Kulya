"use client";

import { LanguageToggle } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { HOME, useAuth } from "@/lib/auth";
import { useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type Notification } from "@/lib/types";
import { DEMO } from "@/lib/format";
import { Activity, Bell, KeyRound, LogOut, type LucideIcon, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
const ROLE_NAME: Record<string, string> = {
  doctor: "Doctor",
  nurse: "Nurse",
  patient: "Patient",
  family: "Family caregiver",
  dietitian: "Renal dietitian",
  org_admin: "Administrator",
};

const ROLE_AREA: Record<string, string> = {
  doctor: "Physician workspace",
  nurse: "Nursing workspace",
  patient: "Patient companion",
  family: "Family access",
  dietitian: "Nutrition workspace",
  org_admin: "Administration",
};

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const subscribeHash = (notify: () => void) => {
  window.addEventListener("hashchange", notify);
  return () => window.removeEventListener("hashchange", notify);
};

/**
 * Application frame: brand and section navigation in a side rail (a scrolling chip row on small
 * screens), a sticky top bar with the page title, notifications, language and account.
 */
export function Shell({
  title,
  back,
  nav = [],
  children,
}: {
  title: string;
  back?: string;
  nav?: NavItem[];
  children: React.ReactNode;
}) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  useLocale();
  const hash = useSyncExternalStore(
    subscribeHash,
    () => window.location.hash,
    () => "",
  );
  const unread = useList<Notification>(user ? "/notifications/?unread=true" : null);
  const unreadCount = unread.data?.length ?? 0;
  // A nav item is either a section of this page (#hash) or another page of the same area (path).
  const current = (
    nav.find((item) => item.href === hash) ??
    nav.find((item) => item.href === pathname) ??
    nav[0]
  )?.href;
  const name = user ? tr(user.display_name || user.username) : "";
  const role = user ? tr(ROLE_NAME[user.role] ?? user.role) : "";
  const home = user ? HOME[user.role] : "/";

  const link = (item: NavItem, compact: boolean) => {
    const active = item.href === current;
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? "true" : undefined}
        className={
          compact
            ? `flex shrink-0 items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium ${active ? "bg-brand text-white" : "bg-chrome text-ink-2"}`
            : `flex min-h-10 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${active ? "bg-brand text-white" : "text-ink-2 hover:bg-brand-soft hover:text-ink"}`
        }
      >
        <Icon className="size-4 shrink-0" aria-hidden />
        <span>{tr(item.label)}</span>
      </Link>
    );
  };

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-e border-line bg-white lg:flex">
        <Link href="/" className="flex items-center gap-3 px-5 py-4">
          <span className="flex size-9 items-center justify-center rounded-lg bg-brand text-white">
            <Activity className="size-5" aria-hidden />
          </span>
          <span>
            <span className="block text-lg leading-tight font-semibold text-brand-strong">
              {tr("Kulya")}
            </span>
            {user && (
              <span className="micro block text-ink-3">{tr(ROLE_AREA[user.role] ?? "")}</span>
            )}
          </span>
        </Link>
        <p className="mx-4 mb-4 flex items-center gap-2 rounded-md bg-chrome px-3 py-2 text-xs text-ink-2">
          <span className="size-2 shrink-0 rounded-full bg-jade" aria-hidden />
          {tr(
            DEMO ? "Synthetic demonstration data" : "Decision support only. Not a medical device.",
          )}
        </p>
        <nav aria-label={tr("Sections")} className="flex-1 space-y-1 overflow-y-auto px-3">
          {nav.map((item) => link(item, false))}
        </nav>
        {user && (
          <div className="m-3 flex items-center gap-3 rounded-lg border border-line bg-chrome p-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-strong text-white">
              <UserRound className="size-5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold">{name}</span>
              <span className="block text-xs text-ink-3">{role}</span>
            </span>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-white/95 backdrop-blur">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 lg:px-8">
            <Link
              href="/"
              className="flex items-center gap-2 font-semibold text-brand-strong lg:hidden"
            >
              <span className="flex size-8 items-center justify-center rounded-lg bg-brand text-white">
                <Activity className="size-4" aria-hidden />
              </span>
              {tr("Kulya")}
            </Link>
            {back && (
              <Link
                href={back}
                className="rounded border border-line bg-white px-2.5 py-1.5 text-sm font-medium text-ink-2 hover:bg-chrome"
              >
                <Tx k="← Back" />
              </Link>
            )}
            <h1 className="text-xl font-semibold text-ink">{tr(title)}</h1>
            <div className="ms-auto flex items-center gap-2">
              {user && (
                <Link
                  href={`${home}#notifications`}
                  aria-label={`${tr("Notifications")}${unreadCount ? ` (${unreadCount} ${tr("unread")})` : ""}`}
                  className="relative flex size-9 items-center justify-center rounded border border-line bg-white text-ink-2 hover:bg-chrome"
                >
                  <Bell className="size-4" aria-hidden />
                  {unreadCount > 0 && (
                    <span className="absolute -end-1.5 -top-1.5 flex min-w-5 items-center justify-center rounded-full bg-bad px-1 text-[11px] font-semibold text-white">
                      {unreadCount}
                    </span>
                  )}
                </Link>
              )}
              <LanguageToggle />
              {user && (
                <Link
                  href="/account/"
                  aria-label={tr("My account")}
                  className="flex size-9 items-center justify-center rounded border border-line bg-white text-ink-2 hover:bg-chrome"
                >
                  <KeyRound className="size-4" aria-hidden />
                </Link>
              )}
              {user && (
                <span data-testid="whoami" className="hidden text-sm text-ink-2 md:inline">
                  {name} · {role}
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  logout();
                  router.replace("/login/");
                }}
              >
                <LogOut className="size-4" aria-hidden />
                <Tx k="Sign out" />
              </Button>
            </div>
          </div>
          {nav.length > 0 && (
            <nav
              aria-label={tr("Sections")}
              className="flex gap-2 overflow-x-auto border-t border-line px-4 py-2 lg:hidden"
            >
              {nav.map((item) => link(item, true))}
            </nav>
          )}
        </header>
        <main className="mx-auto w-full max-w-[1400px] space-y-5 px-4 py-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}

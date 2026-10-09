"use client";

import {
  CalendarDays,
  FileText,
  FlaskConical,
  HeartPulse,
  Salad,
  ShieldCheck,
  UtensilsCrossed,
} from "lucide-react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Load, Section, Stats } from "@/components/feedback";
import { type NavItem, Shell } from "@/components/layout/shell";
import { LabTrends } from "@/features/clinical/components/lab-trends";
import { SessionTable } from "@/features/clinical/components/session-record";
import { NotificationInbox } from "@/features/notifications/components/inbox";
import { MealRecords } from "@/features/nutrition/components/meal-records";
import { ApprovedIdeas } from "@/features/nutrition/components/suggestions";
import { useRole } from "@/lib/auth";
import { dateOnly, weekOf } from "@/lib/format";
import { useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type LabReport, type ReleasedSummary, type Session } from "@/lib/types";

function WeeklyHistory({ sessions }: { sessions: Session[] }) {
  const weeks = new Map<string, number>();
  for (const s of sessions)
    weeks.set(weekOf(s.scheduled_start), (weeks.get(weekOf(s.scheduled_start)) ?? 0) + 1);
  const data = [...weeks.entries()]
    .sort()
    .map(([week, count]) => ({ week: dateOnly(week), sessions: count }));
  return (
    <div
      className="h-44 w-full"
      dir="ltr"
      role="img"
      aria-label={tr("Completed dialysis sessions per week")}
    >
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" fontSize={12} />
          <YAxis allowDecimals={false} fontSize={12} width={30} />
          <Tooltip />
          <Bar dataKey="sessions" fill="#176b87" name={tr("Completed sessions")} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function PatientDashboard() {
  useLocale();
  const user = useRole("patient", "family");
  const upcoming = useList<Session>(
    user ? "/sessions/?status=scheduled&ordering=scheduled_start" : null,
  );
  const completed = useList<Session>(
    user ? "/sessions/?status=completed&ordering=-scheduled_start" : null,
  );
  const summaries = useList<ReleasedSummary>(user ? "/ai/summaries/" : null);
  const labs = useList<LabReport>(user ? "/labs/" : null);
  if (!user) return null;
  const isPatient = user.role === "patient";
  const shared = "Shown only if the patient has shared this with you.";
  const next = upcoming.data?.[0];
  const count = (rows: unknown[] | null) => (rows ? rows.length : "—");
  const nav: NavItem[] = [
    { href: "#summaries", label: "Treatment summaries", icon: FileText },
    { href: "#sessions", label: "Dialysis sessions", icon: CalendarDays },
    { href: "#labs", label: "Laboratory results", icon: FlaskConical },
    // A caregiver may follow several patients, so their meal records stay in the nutrition area.
    ...(isPatient
      ? [
          { href: "#meals", label: "Meal records", icon: UtensilsCrossed },
          { href: "/patient/home/", label: "Family and home", icon: HeartPulse },
        ]
      : [{ href: "/patient/nutrition/", label: "Nutrition", icon: Salad }]),
  ];
  return (
    <Shell title={isPatient ? "My dialysis care" : "Shared with me"} nav={nav}>
      <Stats
        items={[
          {
            label: "Next session",
            value: next ? dateOnly(next.scheduled_start) : "—",
            hint: next ? undefined : "No session scheduled",
            icon: CalendarDays,
          },
          { label: "Completed sessions", value: count(completed.data), tone: "ok" },
          {
            label: "Released summaries",
            value: count(summaries.data),
            hint: "Reviewed and released by a doctor",
            icon: FileText,
          },
          {
            label: "Released lab reports",
            value: count(labs.data),
            hint: "Released by a doctor",
            icon: FlaskConical,
          },
        ]}
      />
      <Section
        id="summaries"
        icon={FileText}
        title="Treatment summaries"
        description="Each summary was reviewed and released by a doctor. Discuss any question with your care team."
      >
        <Load
          from={summaries}
          empty={
            isPatient ? "No summaries have been released yet." : "No summaries are shared with you."
          }
        >
          {(rows) => (
            <ul className="space-y-3">
              {rows.map((s) => (
                <li key={s.id} className="rounded-lg border border-line bg-chrome p-4">
                  <span className="micro mb-2 inline-flex items-center gap-1 rounded border border-ok/20 bg-ok-soft px-1.5 text-ok">
                    <ShieldCheck className="size-3" aria-hidden />
                    {tr("Doctor reviewed")}
                  </span>
                  <p className="text-sm text-ink-3">
                    {!isPatient && `${tr(s.patient_name)} · `}
                    {tr("Session of")} {dateOnly(s.session_date)} · {tr("released")}{" "}
                    {dateOnly(s.released_at)}
                  </p>
                  <p className="mt-1 text-lg leading-8 text-ink">{tr(s.text ?? "")}</p>
                </li>
              ))}
            </ul>
          )}
        </Load>
      </Section>

      <Section
        id="sessions"
        icon={CalendarDays}
        title="Dialysis sessions"
        description={isPatient ? "Sessions per week, then the most recent ones." : shared}
      >
        <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
          <div>
            <h3 className="mb-2 text-sm font-medium">
              <Tx k="Upcoming sessions" />
            </h3>
            <Load from={upcoming} empty="No upcoming sessions to show.">
              {(rows) => <SessionTable sessions={rows} />}
            </Load>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium">
              <Tx k="Completed sessions" />
            </h3>
            <Load from={completed} empty="No completed sessions to show.">
              {(rows) => (
                <>
                  <WeeklyHistory sessions={rows} />
                  <SessionTable sessions={rows.slice(0, 6)} />
                </>
              )}
            </Load>
          </div>
        </div>
      </Section>

      <Section
        id="labs"
        icon={FlaskConical}
        title="Laboratory results"
        description="Only results a doctor has released are shown."
      >
        <Load from={labs} empty="No laboratory results to show.">
          {(rows) => <LabTrends reports={rows} />}
        </Load>
      </Section>

      {isPatient && (
        <MealRecords
          diary={() => "/patient/nutrition/history/"}
          action={
            <Link
              href="/patient/nutrition/"
              className="inline-flex min-h-9 items-center gap-2 rounded-md bg-brand px-3 text-sm font-medium text-white hover:bg-brand-strong"
            >
              <Salad className="size-4" aria-hidden />
              <Tx k="Nutrition" />
            </Link>
          }
        >
          <ApprovedIdeas />
        </MealRecords>
      )}
      <NotificationInbox />
    </Shell>
  );
}

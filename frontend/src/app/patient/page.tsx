"use client";

import { CalendarDays, FileText, FlaskConical, HeartPulse, Salad, Share2, ShieldCheck } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";

import {
  ErrorNote,
  LabTrends,
  Load,
  type NavItem,
  NotificationInbox,
  requiredText,
  Section,
  SessionTable,
  Shell,
  Stats,
  ZForm,
} from "@/components/app";
import { Button } from "@/components/ui/button";
import { api, type Consent, type LabReport, type ReleasedSummary, type Session, type Vital } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { dateOnly, dateTime, label, weekOf, withUnit } from "@/lib/format";
import { useAction, useList } from "@/lib/hooks";

const HOME_UNITS: Record<string, string> = { weight: "kg", systolic_bp: "mmHg", diastolic_bp: "mmHg", heart_rate: "bpm" };
const measurementSchema = z.object({ kind: z.string(), value: z.coerce.number({ message: "Enter a number." }) });
const consentSchema = z.object({
  caregiver_username: requiredText("Caregiver username"),
  share: z.enum([
    "summaries",
    "summaries,appointments",
    "summaries,appointments,labs",
    "summaries,appointments,labs,nutrition",
    "summaries,appointments,labs,nutrition,nutrition_log",
  ]),
});

function WeeklyHistory({ sessions }: { sessions: Session[] }) {
  const weeks = new Map<string, number>();
  for (const s of sessions) weeks.set(weekOf(s.scheduled_start), (weeks.get(weekOf(s.scheduled_start)) ?? 0) + 1);
  const data = [...weeks.entries()].sort().map(([week, count]) => ({ week: dateOnly(week), sessions: count }));
  return (
    <div className="h-44 w-full" dir="ltr" role="img" aria-label={tr("Completed dialysis sessions per week")}>
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

function FamilySharing() {
  const grants = useList<Consent>("/consent/");
  const revoke = useAction();
  return (
    <Section id="sharing" icon={Share2} title="Family sharing" description="You decide what a family caregiver can see. You can stop sharing at any time.">
      <Load from={grants} empty="You are not sharing with anyone.">
        {(rows) => (
          <ul className="mb-4 divide-y divide-line text-sm">
            {rows.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-3 py-2">
                <span className="font-medium">{c.caregiver_name}</span>
                <span>{c.scopes.map(label).join(", ")}</span>
                {c.revoked_at ? (
                  <span className="text-ink-3">{tr("Stopped")} {dateOnly(c.revoked_at)}</span>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    className="ms-auto"
                    disabled={revoke.pending}
                    onClick={async () => (await revoke.run(() => api.post(`/consent/${c.id}/revoke/`))) && grants.reload()}
                  >
                    <Tx k="Stop sharing" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Load>
      <ErrorNote message={revoke.error} />
      <ZForm
        schema={consentSchema}
        submitLabel="Share with caregiver"
        fields={[
          { name: "caregiver_username", label: "Caregiver username" },
          {
            name: "share",
            label: "What to share",
            type: "select",
            options: [
              ["summaries", "Reviewed summaries"],
              ["summaries,appointments", "Summaries and appointments"],
              ["summaries,appointments,labs", "Summaries, appointments and released lab results"],
              ["summaries,appointments,labs,nutrition", "All of the above and my food diary"],
              ["summaries,appointments,labs,nutrition,nutrition_log", "All of the above, and they may record meals for me"],
            ],
          },
        ]}
        onSubmit={async (values) => {
          await api.post("/consent/", { caregiver_username: values.caregiver_username, scopes: values.share.split(",") });
          grants.reload();
        }}
      />
    </Section>
  );
}

function HomeMeasurements() {
  const mine = useList<Vital>("/vitals/?ordering=-recorded_at");
  return (
    <Section id="home" icon={HeartPulse} title="Home measurements" description="Measurements you enter are marked as patient-reported for your care team.">
      <ZForm
        schema={measurementSchema}
        submitLabel="Submit measurement"
        fields={[
          {
            name: "kind",
            label: "Measurement",
            type: "select",
            options: Object.entries(HOME_UNITS).map(([kind, unit]): [string, string] => [kind, `${label(kind)} (${unit})`]),
          },
          { name: "value", label: "Value", type: "number" },
        ]}
        onSubmit={async (values) => {
          await api.post("/vitals/", { ...values, phase: "pre", recorded_at: new Date().toISOString() });
          mine.reload();
        }}
      />
      <div className="mt-4">
        <Load from={mine} empty="You have not submitted any measurements.">
          {(rows) => (
            <ul className="divide-y divide-line text-sm">
              {rows.slice(0, 8).map((v) => (
                <li key={v.id} className="flex gap-3 py-2">
                  <span>{label(v.kind)}</span>
                  <span className="font-medium">{withUnit(v.value, v.unit)}</span>
                  <time className="ms-auto text-ink-3">{dateTime(v.recorded_at)}</time>
                </li>
              ))}
            </ul>
          )}
        </Load>
      </div>
    </Section>
  );
}

export default function PatientDashboard() {
  useLocale();
  const user = useRole("patient", "family");
  const upcoming = useList<Session>(user ? "/sessions/?status=scheduled&ordering=scheduled_start" : null);
  const completed = useList<Session>(user ? "/sessions/?status=completed&ordering=-scheduled_start" : null);
  const summaries = useList<ReleasedSummary>(user ? "/ai/summaries/" : null);
  const labs = useList<LabReport>(user ? "/labs/" : null);
  if (!user) return null;
  const isPatient = user.role === "patient";
  const shared = "Shown only if the patient has shared this with you.";
  const next = upcoming.data?.[0];
  const count = (rows: unknown[] | null) => (rows ? rows.length : "—");
  const nav: NavItem[] = [
    { href: "#summaries", label: "Treatment summaries", icon: FileText },
    { href: "#sessions", label: "Upcoming sessions", icon: CalendarDays },
    { href: "#labs", label: "Laboratory results", icon: FlaskConical },
    { href: "/patient/nutrition/", label: "Nutrition", icon: Salad },
    ...(isPatient
      ? [
          { href: "#sharing", label: "Family sharing", icon: Share2 },
          { href: "#home", label: "Home measurements", icon: HeartPulse },
        ]
      : []),
  ];
  return (
    <Shell title={isPatient ? "My dialysis care" : "Shared with me"} nav={nav}>
      <Stats
        items={[
          { label: "Next session", value: next ? dateOnly(next.scheduled_start) : "—", hint: next ? undefined : "No session scheduled", icon: CalendarDays },
          { label: "Completed sessions", value: count(completed.data), tone: "ok" },
          { label: "Released summaries", value: count(summaries.data), hint: "Reviewed and released by a doctor", icon: FileText },
          { label: "Released lab reports", value: count(labs.data), hint: "Released by a doctor", icon: FlaskConical },
        ]}
      />
      <Section
        id="summaries"
        icon={FileText}
        title="Treatment summaries"
        description="Each summary was reviewed and released by a doctor. Discuss any question with your care team."
      >
        <Load from={summaries} empty={isPatient ? "No summaries have been released yet." : "No summaries are shared with you."}>
          {(rows) => (
            <ul className="space-y-3">
              {rows.map((s) => (
                <li key={s.id} className="rounded-lg border border-line bg-chrome p-4">
                  <span className="micro mb-2 inline-flex items-center gap-1 rounded border border-ok/20 bg-ok-soft px-1.5 text-ok">
                    <ShieldCheck className="size-3" aria-hidden />
                    {tr("Doctor reviewed")}
                  </span>
                  <p className="text-sm text-ink-3">
                    {!isPatient && `${s.patient_name} · `}{tr("Session of")} {dateOnly(s.session_date)} · {tr("released")} {dateOnly(s.released_at)}
                  </p>
                  <p className="mt-1 text-lg leading-8 text-ink">{s.text}</p>
                </li>
              ))}
            </ul>
          )}
        </Load>
      </Section>

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <Section id="sessions" icon={CalendarDays} title="Upcoming sessions" description={isPatient ? undefined : shared}>
          <Load from={upcoming} empty="No upcoming sessions to show.">
            {(rows) => <SessionTable sessions={rows} />}
          </Load>
        </Section>
        <Section title="Completed sessions" description={isPatient ? "Sessions per week, then the most recent ones." : shared}>
          <Load from={completed} empty="No completed sessions to show.">
            {(rows) => (
              <>
                <WeeklyHistory sessions={rows} />
                <SessionTable sessions={rows.slice(0, 6)} />
              </>
            )}
          </Load>
        </Section>
      </div>

      <Section id="labs" icon={FlaskConical} title="Laboratory results" description="Only results a doctor has released are shown.">
        <Load from={labs} empty="No laboratory results to show.">
          {(rows) => <LabTrends reports={rows} />}
        </Load>
      </Section>

      {isPatient && (
        <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
          <FamilySharing />
          <HomeMeasurements />
        </div>
      )}
      <NotificationInbox />
    </Shell>
  );
}

"use client";

import { Bell, CalendarDays, MessageSquare, Users } from "lucide-react";
import Link from "next/link";
import { z } from "zod";

import { Load, Section, Stats } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { type NavItem, Shell } from "@/components/layout/shell";
import { SessionTable } from "@/features/clinical/components/session-record";
import { NotificationInbox } from "@/features/notifications/components/inbox";
import { api } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { dateTime, label, today } from "@/lib/format";
import { useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type Feedback, type Patient, type Session } from "@/lib/types";

const scheduleSchema = z.object({
  patient: z.string().min(1, "Choose a patient."),
  scheduled_start: z.string().min(1, "Choose a date and time."),
});

const NAV: NavItem[] = [
  { href: "#schedule", label: "Today's dialysis schedule", icon: CalendarDays },
  { href: "#patients", label: "Assigned patients", icon: Users },
  { href: "#feedback", label: "Doctor feedback inbox", icon: MessageSquare },
  { href: "#notifications", label: "Notifications", icon: Bell },
];
const count = (rows: unknown[] | null) => (rows ? rows.length : "—");

export default function NurseDashboard() {
  useLocale();
  const user = useRole("nurse");
  const patients = useList<Patient>(user ? "/patients/" : null);
  const schedule = useList<Session>(
    user ? `/sessions/?date=${today()}&ordering=scheduled_start` : null,
  );
  const feedback = useList<Feedback>(user ? "/doctor/feedback/" : null);
  if (!user) return null;
  return (
    <Shell title="Nurse dashboard" nav={NAV}>
      <Stats
        items={[
          {
            label: "Sessions today",
            value: count(schedule.data),
            hint: "Scheduled for today",
            icon: CalendarDays,
          },
          {
            label: "In progress now",
            value: schedule.data
              ? schedule.data.filter((s) => s.status === "in_progress").length
              : "—",
            hint: "Sessions currently running",
            tone: "ai",
          },
          {
            label: "Assigned patients",
            value: count(patients.data),
            hint: "On your care team",
            icon: Users,
          },
          {
            label: "Doctor feedback",
            value: count(feedback.data),
            hint: "Messages from doctors",
            icon: MessageSquare,
          },
        ]}
      />
      <div className="grid gap-5 xl:grid-cols-3 xl:items-start">
        <div className="space-y-5 xl:col-span-2">
          <Section
            id="schedule"
            icon={CalendarDays}
            title="Today's dialysis schedule"
            description="Open a session to start it and document care."
          >
            <Load from={schedule} empty="No sessions are scheduled for today.">
              {(rows) => (
                <SessionTable sessions={rows} hrefFor={(s) => `/nurse/sessions/${s.id}/`} />
              )}
            </Load>
          </Section>

          <Section
            id="patients"
            icon={Users}
            title="Assigned patients"
            description="Only patients on your care team are listed."
          >
            <Load from={patients} empty="No patients are assigned to you.">
              {(rows) => (
                <>
                  <ul className="mb-4 divide-y divide-line text-sm">
                    {rows.map((p) => (
                      <li key={p.id} className="flex gap-3 py-2">
                        <span className="text-ink-3">{p.mrn}</span>
                        <span className="font-medium">{tr(p.full_name ?? "")}</span>
                        <Link
                          className="ms-auto font-medium text-brand hover:underline"
                          href={`/doctor/patients/${p.id}/nutrition/`}
                        >
                          <Tx k="Nutrition" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <h3 className="mb-2 text-sm font-medium">
                    <Tx k="Schedule a session" />
                  </h3>
                  <ZForm
                    schema={scheduleSchema}
                    submitLabel="Schedule session"
                    fields={[
                      {
                        name: "patient",
                        label: "Patient",
                        type: "select",
                        options: rows.map((p): [string, string] => [
                          p.id,
                          `${p.mrn} — ${tr(p.full_name)}`,
                        ]),
                      },
                      { name: "scheduled_start", label: "Start", type: "datetime-local" },
                    ]}
                    onSubmit={async (values) => {
                      await api.post("/sessions/", {
                        patient: values.patient,
                        scheduled_start: new Date(values.scheduled_start).toISOString(),
                      });
                      schedule.reload();
                    }}
                  />
                </>
              )}
            </Load>
          </Section>
        </div>
        <aside className="space-y-5">
          <Section
            id="feedback"
            icon={MessageSquare}
            title="Doctor feedback inbox"
            description="Feedback and clarification requests on your patients' sessions."
          >
            <Load from={feedback} empty="No feedback yet.">
              {(rows) => (
                <ul className="divide-y divide-line text-sm">
                  {rows.slice(0, 10).map((f) => (
                    <li key={f.id} className="py-2">
                      <div className="flex flex-wrap gap-2">
                        <span className="font-medium">{label(f.kind)}</span>
                        <span className="text-ink-3">{tr(f.author_name ?? "")}</span>
                        <time className="ms-auto text-ink-3">{dateTime(f.created_at)}</time>
                      </div>
                      <p dir="auto">{tr(f.text ?? "")}</p>
                      <Link
                        className="font-medium text-brand hover:underline"
                        href={`/nurse/sessions/${f.session}/`}
                      >
                        <Tx k="Open session" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Load>
          </Section>
          <NotificationInbox />
        </aside>
      </div>
    </Shell>
  );
}

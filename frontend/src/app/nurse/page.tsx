"use client";

import Link from "next/link";
import { z } from "zod";

import { Load, NotificationInbox, Section, SessionTable, Shell, ZForm } from "@/components/app";
import { api, type Feedback, type Patient, type Session } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { dateTime, label, today } from "@/lib/format";
import { useList } from "@/lib/hooks";

const scheduleSchema = z.object({
  patient: z.string().min(1, "Choose a patient."),
  scheduled_start: z.string().min(1, "Choose a date and time."),
});

export default function NurseDashboard() {
  const user = useRole("nurse");
  const patients = useList<Patient>(user ? "/patients/" : null);
  const schedule = useList<Session>(user ? `/sessions/?date=${today()}&ordering=scheduled_start` : null);
  const feedback = useList<Feedback>(user ? "/doctor/feedback/" : null);
  if (!user) return null;
  return (
    <Shell title="Nurse dashboard">
      <Section title="Today's dialysis schedule" description="Open a session to start it and document care.">
        <Load from={schedule} empty="No sessions are scheduled for today.">
          {(rows) => <SessionTable sessions={rows} hrefFor={(s) => `/nurse/sessions/${s.id}/`} />}
        </Load>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Assigned patients" description="Only patients on your care team are listed.">
          <Load from={patients} empty="No patients are assigned to you.">
            {(rows) => (
              <>
                <ul className="mb-4 divide-y text-sm">
                  {rows.map((p) => (
                    <li key={p.id} className="flex gap-3 py-2">
                      <span className="text-slate-500">{p.mrn}</span>
                      <span className="font-medium">{p.full_name}</span>
                    </li>
                  ))}
                </ul>
                <h3 className="mb-2 text-sm font-medium">Schedule a session</h3>
                <ZForm
                  schema={scheduleSchema}
                  submitLabel="Schedule session"
                  fields={[
                    {
                      name: "patient",
                      label: "Patient",
                      type: "select",
                      options: rows.map((p): [string, string] => [p.id, `${p.mrn} — ${p.full_name}`]),
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

        <Section title="Doctor feedback inbox" description="Feedback and clarification requests on your patients' sessions.">
          <Load from={feedback} empty="No feedback yet.">
            {(rows) => (
              <ul className="divide-y text-sm">
                {rows.slice(0, 10).map((f) => (
                  <li key={f.id} className="py-2">
                    <div className="flex flex-wrap gap-2">
                      <span className="font-medium">{label(f.kind)}</span>
                      <span className="text-slate-500">{f.author_name}</span>
                      <time className="ml-auto text-slate-500">{dateTime(f.created_at)}</time>
                    </div>
                    <p dir="auto">{f.text}</p>
                    <Link className="text-teal-800 underline" href={`/nurse/sessions/${f.session}/`}>
                      Open session
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Load>
        </Section>
      </div>
      <NotificationInbox />
    </Shell>
  );
}

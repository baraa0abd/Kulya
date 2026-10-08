"use client";

import { useParams } from "next/navigation";
import { z } from "zod";

import { Load, Measurements, optionalNumber, requiredText, Section, Shell, Status, Timeline, ZForm } from "@/components/app";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Feedback, type Finding, type SessionDetail } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { dateTime, label } from "@/lib/format";
import { useGet, useList } from "@/lib/hooks";

const options = (values: string[]): [string, string][] => values.map((v) => [v, label(v)]);
const now = () => new Date().toISOString();

// kind -> unit shown next to the field. The server enforces the unit and the plausible range.
const VITALS: Record<string, string> = {
  systolic_bp: "mmHg",
  diastolic_bp: "mmHg",
  heart_rate: "bpm",
  temperature: "degC",
  spo2: "%",
  weight: "kg",
};
const READINGS: Record<string, string> = {
  blood_flow_rate: "mL/min",
  dialysate_flow_rate: "mL/min",
  venous_pressure: "mmHg",
  arterial_pressure: "mmHg",
  uf_rate: "mL/h",
  uf_removed: "mL",
};
const withUnits = (table: Record<string, string>): [string, string][] =>
  Object.entries(table).map(([kind, unit]) => [kind, `${label(kind)} (${unit})`]);

const number = z.coerce.number({ message: "Enter a number." });
const vitalSchema = z.object({ kind: z.string(), phase: z.enum(["pre", "intra", "post"]), value: number });
const readingSchema = z.object({ kind: z.string(), value: number });
const actionSchema = z.object({ action_type: z.string(), description: requiredText("Description"), reason: z.string() });
const eventSchema = z.object({ event_type: z.string(), description: requiredText("Description") });
const noteSchema = z.object({ text: requiredText("Note") });
const resolveSchema = z.object({ resolution: requiredText("Resolution") });
const startSchema = z.object({ pre_weight_kg: optionalNumber(20, 300) });
const completeSchema = z.object({ post_weight_kg: optionalNumber(20, 300), uf_volume_ml: optionalNumber(0, 10000) });

export default function NurseSessionPage() {
  useLocale();
  const user = useRole("nurse");
  const { id } = useParams<{ id: string }>();
  const session = useGet<SessionDetail>(user ? `/sessions/${id}/` : null);
  const checks = useGet<{ rule_findings: Finding[]; checked_at: string | null }>(
    user ? `/ai/reviews/completeness/?session=${id}` : null,
  );
  const feedback = useList<Feedback>(user ? `/doctor/feedback/?session=${id}` : null);
  if (!user) return null;
  const refresh = () => {
    session.reload();
    checks.reload();
  };
  const save = (path: string, extra: () => Record<string, unknown>) => async (values: Record<string, unknown>) => {
    await api.post(path, { session: id, ...values, ...extra() });
    refresh();
  };

  return (
    <Shell title="Dialysis session" back="/nurse/">
      <Load from={session}>
        {(s) => (
          <>
            <Section title={`${s.patient_name} · ${tr("scheduled")} ${dateTime(s.scheduled_start)}`} action={<Status value={s.status} />}>
              {s.status === "scheduled" && (
                <ZForm
                  schema={startSchema}
                  submitLabel="Start session"
                  fields={[{ name: "pre_weight_kg", label: "Pre-treatment weight (kg)", type: "number" }]}
                  onSubmit={async (values) => {
                    await api.post(`/sessions/${id}/start/`, values);
                    refresh();
                  }}
                />
              )}
              {s.status !== "scheduled" && <Measurements session={s} />}
              {s.status === "in_progress" && (
                <div className="mt-4 border-t pt-4">
                  <h3 className="mb-2 text-sm font-medium"><Tx k="Complete the session" /></h3>
                  <ZForm
                    schema={completeSchema}
                    submitLabel="Complete session"
                    fields={[
                      { name: "post_weight_kg", label: "Post-treatment weight (kg)", type: "number" },
                      { name: "uf_volume_ml", label: "Ultrafiltration volume (mL)", type: "number" },
                    ]}
                    onSubmit={async (values) => {
                      await api.post(`/sessions/${id}/complete/`, values);
                      refresh();
                    }}
                  />
                </div>
              )}
            </Section>

            {s.status !== "scheduled" && (
              <Section
                title="Document care"
                description="Signed entries cannot be edited. To correct one, add a new entry that explains the correction."
              >
                <Tabs defaultValue="vital">
                  <TabsList>
                    <TabsTrigger value="vital"><Tx k="Vital sign" /></TabsTrigger>
                    <TabsTrigger value="action"><Tx k="Nursing action" /></TabsTrigger>
                    <TabsTrigger value="reading"><Tx k="Machine reading" /></TabsTrigger>
                    <TabsTrigger value="event"><Tx k="Event / incident" /></TabsTrigger>
                    <TabsTrigger value="note"><Tx k="Note" /></TabsTrigger>
                  </TabsList>
                  <TabsContent value="vital" className="pt-3">
                    <ZForm
                      schema={vitalSchema}
                      submitLabel="Record vital sign"
                      fields={[
                        { name: "kind", label: "Measurement", type: "select", options: withUnits(VITALS) },
                        { name: "phase", label: "When", type: "select", options: [["pre", "Before treatment"], ["intra", "During treatment"], ["post", "After treatment"]] },
                        { name: "value", label: "Value", type: "number", hint: "Enter the value in the unit shown." },
                      ]}
                      onSubmit={save("/vitals/", () => ({ recorded_at: now() }))}
                    />
                  </TabsContent>
                  <TabsContent value="action" className="pt-3">
                    <ZForm
                      schema={actionSchema}
                      submitLabel="Record nursing action"
                      fields={[
                        {
                          name: "action_type",
                          label: "Action",
                          type: "select",
                          options: options(["access_care", "uf_adjustment", "treatment_pause", "fluid_bolus", "position_change", "physician_notified", "other"]),
                        },
                        { name: "description", label: "What was done", type: "textarea" },
                        { name: "reason", label: "Reason", type: "textarea", hint: "An action without a reason is flagged as incomplete." },
                      ]}
                      onSubmit={save("/nursing-actions/", () => ({ performed_at: now() }))}
                    />
                  </TabsContent>
                  <TabsContent value="reading" className="pt-3">
                    <ZForm
                      schema={readingSchema}
                      submitLabel="Record machine reading"
                      fields={[
                        { name: "kind", label: "Reading", type: "select", options: withUnits(READINGS) },
                        { name: "value", label: "Value", type: "number", hint: "Typed from the machine display. The system does not connect to the machine." },
                      ]}
                      onSubmit={save("/device-readings/", () => ({ recorded_at: now() }))}
                    />
                  </TabsContent>
                  <TabsContent value="event" className="pt-3">
                    <ZForm
                      schema={eventSchema}
                      submitLabel="Record event"
                      fields={[
                        {
                          name: "event_type",
                          label: "Type",
                          type: "select",
                          options: options(["symptom", "hypotension", "cramps", "clotting", "machine_alarm", "access_issue", "incident", "other"]),
                        },
                        { name: "description", label: "What happened", type: "textarea" },
                      ]}
                      onSubmit={save("/session-events/", () => ({ occurred_at: now() }))}
                    />
                  </TabsContent>
                  <TabsContent value="note" className="pt-3">
                    <ZForm
                      schema={noteSchema}
                      submitLabel="Add note"
                      fields={[{ name: "text", label: "Nursing note", type: "textarea" }]}
                      onSubmit={save("/nursing-notes/", () => ({}))}
                    />
                  </TabsContent>
                </Tabs>
              </Section>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <Section
                title="Documentation completeness"
                description="Automated checks on what is recorded. They do not judge clinical decisions."
              >
                <Load from={checks}>
                  {(result) =>
                    result.checked_at === null ? (
                      <p className="text-sm text-slate-500"><Tx k="Checks run after the first nursing action is recorded." /></p>
                    ) : result.rule_findings.length === 0 ? (
                      <p className="text-sm text-teal-800">{tr("No documentation gaps found")} ({dateTime(result.checked_at)}).</p>
                    ) : (
                      <ul className="list-disc space-y-1 ps-5 text-sm" data-testid="completeness">
                        {result.rule_findings.map((f) => (
                          <li key={f.finding_id}>
                            <span className="font-medium">{label(f.check)}:</span> {f.description}
                          </li>
                        ))}
                      </ul>
                    )
                  }
                </Load>
              </Section>
              <Section title="Doctor feedback on this session">
                <Load from={feedback} empty="No feedback on this session.">
                  {(rows) => (
                    <ul className="divide-y text-sm">
                      {rows.map((f) => (
                        <li key={f.id} className="py-2">
                          <span className="font-medium">{label(f.kind)}</span> · {f.author_name} · {dateTime(f.created_at)}
                          <p dir="auto">{f.text}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </Load>
              </Section>
            </div>

            <Section title="Nursing action timeline">
              <Timeline
                session={s}
                renderEvent={(event) =>
                  event.resolved_at ? null : (
                    <div className="mt-2">
                      <ZForm
                        schema={resolveSchema}
                        submitLabel="Document resolution"
                        fields={[{ name: "resolution", label: "Resolution", type: "textarea" }]}
                        onSubmit={async (values) => {
                          await api.post(`/session-events/${event.id}/resolve/`, values);
                          refresh();
                        }}
                      />
                    </div>
                  )
                }
              />
            </Section>
          </>
        )}
      </Load>
    </Shell>
  );
}

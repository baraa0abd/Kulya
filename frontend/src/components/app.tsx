"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { type FieldValues, useForm } from "react-hook-form";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  type DeviceReading,
  type LabReport,
  type Notification,
  type NursingAction,
  type NursingNote,
  type Session,
  type SessionDetail,
  type SessionEvent,
  type Vital,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateOnly, dateTime, label, minutesBetween, timeOnly, withUnit } from "@/lib/format";
import { setLocale, tr, Tx, useLocale } from "@/lib/i18n";
import { type Loaded, useAction, useList } from "@/lib/hooks";

// ---------------------------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------------------------

const ROLE_NAME: Record<string, string> = {
  doctor: "Doctor",
  nurse: "Nurse",
  patient: "Patient",
  family: "Family caregiver",
};

export function Shell({ title, back, children }: { title: string; back?: string; children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  useLocale();
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <Link href="/" className="text-lg font-semibold text-teal-800">
            <Tx k="Kulya" />
          </Link>
          <span className="text-sm text-slate-500"><Tx k="Synthetic demonstration data" /></span>
          <div className="ms-auto flex items-center gap-3 text-sm">
            {user && (
              <span data-testid="whoami">
                {user.display_name || user.username} · {tr(ROLE_NAME[user.role] ?? user.role)}
              </span>
            )}
            <LanguageToggle />
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                logout();
                router.replace("/login/");
              }}
            >
              <Tx k="Sign out" />
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl space-y-4 px-4 py-6">
        <div className="flex flex-wrap items-center gap-3">
          {back && (
            <Link href={back} className="text-sm text-teal-800 underline">
              <Tx k="← Back" />
            </Link>
          )}
          <h1 className="text-2xl font-semibold text-slate-900">{tr(title)}</h1>
        </div>
        {children}
      </main>
    </div>
  );
}

export function Section({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
        <div>
          <CardTitle>
            <h2>{tr(title)}</h2>
          </CardTitle>
          {description && <CardDescription>{tr(description)}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Loading, error and empty states for anything fetched. */
export function Load<T>({
  from,
  empty,
  children,
}: {
  from: Loaded<T>;
  empty?: string;
  children: (data: T) => React.ReactNode;
}) {
  if (from.loading) return <p className="text-sm text-slate-500"><Tx k="Loading…" /></p>;
  if (from.error) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-red-700">
        <span>{from.error}</span>
        <Button variant="outline" size="sm" onClick={from.reload}>
          <Tx k="Retry" />
        </Button>
      </div>
    );
  }
  if (from.data === null || (Array.isArray(from.data) && from.data.length === 0)) {
    return <p className="text-sm text-slate-500">{tr(empty ?? "Nothing to show yet.")}</p>;
  }
  return <>{children(from.data)}</>;
}

/** Switches between Arabic (right-to-left, default) and English. */
export function LanguageToggle() {
  const locale = useLocale();
  return (
    <Button variant="ghost" size="sm" onClick={() => setLocale(locale === "ar" ? "en" : "ar")}>
      {locale === "ar" ? "English" : "العربية"}
    </Button>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="text-sm text-red-700">
      {message}
    </p>
  ) : null;
}

const STATUS_STYLE: Record<string, string> = {
  scheduled: "bg-slate-100 text-slate-800",
  in_progress: "bg-blue-100 text-blue-900",
  completed: "bg-teal-100 text-teal-900",
  pending_review: "bg-amber-100 text-amber-900",
  unverified: "bg-amber-100 text-amber-900",
  open: "bg-amber-100 text-amber-900",
  ai_unavailable: "bg-red-100 text-red-900",
  rejected: "bg-red-100 text-red-900",
  verified: "bg-teal-100 text-teal-900",
  reviewed: "bg-teal-100 text-teal-900",
  released: "bg-teal-100 text-teal-900",
};

export function Status({ value }: { value: string }) {
  useLocale();
  return <Badge className={STATUS_STYLE[value] ?? "bg-slate-100 text-slate-800"}>{label(value)}</Badge>;
}

/** Every piece of AI-written content is shown under this label. */
export function AiLabel({ text }: { text: string }) {
  return (
    <p className="rounded border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900" data-testid="ai-label">
      <strong><Tx k="AI-generated." /></strong> {tr(text.replace(/^AI-generated draft\.\s*/, ""))}
    </p>
  );
}

// ---------------------------------------------------------------------------------------------
// Forms (React Hook Form + Zod)
// ---------------------------------------------------------------------------------------------

export interface FieldSpec {
  name: string;
  label: string;
  type?: "text" | "password" | "number" | "textarea" | "select" | "datetime-local";
  options?: [value: string, text: string][];
  hint?: string;
}

/** Empty input -> undefined, otherwise a number. For optional numeric fields. */
export const optionalNumber = (min: number, max: number) =>
  z.preprocess((v) => (v === "" || v === null || v === undefined ? undefined : Number(v)), z.number().min(min).max(max).optional());
export const requiredText = (what: string) => z.string().trim().min(1, `${what} is required.`);

export function ZForm<S extends z.ZodType>({
  schema,
  fields,
  submitLabel,
  onSubmit,
  defaults,
}: {
  schema: S;
  fields: FieldSpec[];
  submitLabel: string;
  onSubmit: (values: z.output<S>) => Promise<unknown>;
  defaults?: Record<string, string>;
}) {
  const initial = useMemo(
    () => Object.fromEntries(fields.map((f) => [f.name, defaults?.[f.name] ?? f.options?.[0]?.[0] ?? ""])),
    [fields, defaults],
  );
  const form = useForm<FieldValues>({ resolver: zodResolver(schema as never) as never, defaultValues: initial });
  const action = useAction();
  useLocale();
  const submit = form.handleSubmit(async (values) => {
    if (await action.run(() => onSubmit(values as z.output<S>))) form.reset(initial);
  });
  const control = "w-full rounded-md border border-input bg-white px-3 py-2 text-sm";
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" noValidate>
      {fields.map((field) => {
        const id = `${submitLabel}-${field.name}`.replaceAll(" ", "-");
        const error = form.formState.errors[field.name]?.message;
        const wide = field.type === "textarea" ? "sm:col-span-2" : "";
        return (
          <div key={field.name} className={`space-y-1 ${wide}`}>
            <Label htmlFor={id}>{tr(field.label)}</Label>
            {field.type === "textarea" ? (
              <Textarea id={id} rows={3} dir="auto" {...form.register(field.name)} />
            ) : field.type === "select" ? (
              <select id={id} className={control} {...form.register(field.name)}>
                {field.options?.map(([value, text]) => (
                  <option key={value} value={value}>
                    {tr(text)}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                id={id}
                type={field.type === "number" ? "text" : (field.type ?? "text")}
                inputMode={field.type === "number" ? "decimal" : undefined}
                {...form.register(field.name)}
              />
            )}
            {field.hint && <p className="text-xs text-slate-500">{tr(field.hint)}</p>}
            {typeof error === "string" && (
              <p role="alert" className="text-xs text-red-700">
                {tr(error)}
              </p>
            )}
          </div>
        );
      })}
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={action.pending}>
          {action.pending ? tr("Saving…") : tr(submitLabel)}
        </Button>
        <ErrorNote message={action.error} />
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------------------------
// Shared clinical widgets
// ---------------------------------------------------------------------------------------------

export function SessionTable({ sessions, hrefFor }: { sessions: Session[]; hrefFor?: (s: Session) => string }) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead><Tx k="Date" /></TableHead>
            <TableHead><Tx k="Patient" /></TableHead>
            <TableHead><Tx k="Status" /></TableHead>
            <TableHead><Tx k="Documented duration" /></TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sessions.map((s) => (
            <TableRow key={s.id}>
              <TableCell>{dateTime(s.started_at ?? s.scheduled_start)}</TableCell>
              <TableCell>{s.patient_name}</TableCell>
              <TableCell>
                <Status value={s.status} />
              </TableCell>
              <TableCell>{withUnit(minutesBetween(s.started_at, s.ended_at), "min")}</TableCell>
              <TableCell className="text-end">
                {hrefFor && (
                  <Link className="text-teal-800 underline" href={hrefFor(s)}>
                    <Tx k="Open" />
                  </Link>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function Measurements({ session }: { session: SessionDetail }) {
  useLocale();
  const missing = tr("Not recorded");
  const rows: [string, string, string][] = [
    [tr("Prescribed duration"), withUnit(session.prescribed_duration_minutes, "min"), tr("prescribed")],
    [tr("Documented duration"), withUnit(minutesBetween(session.started_at, session.ended_at), "min"), tr("calculated")],
    [tr("Pre-treatment weight"), withUnit(session.pre_weight_kg, "kg"), tr("measured")],
    [tr("Post-treatment weight"), withUnit(session.post_weight_kg, "kg"), tr("measured")],
    [tr("Ultrafiltration volume"), withUnit(session.uf_volume_ml, "mL"), tr("measured")],
    ...session.vitals.map((v: Vital): [string, string, string] => [
      `${label(v.kind)} (${tr(v.phase)}, ${timeOnly(v.recorded_at)})`,
      withUnit(v.value, v.unit),
      label(v.source),
    ]),
    ...session.device_readings.map((r: DeviceReading): [string, string, string] => [
      `${label(r.kind)} (${timeOnly(r.recorded_at)})`,
      withUnit(r.value, r.unit),
      label(r.source),
    ]),
  ];
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead><Tx k="Measurement" /></TableHead>
            <TableHead><Tx k="Value" /></TableHead>
            <TableHead><Tx k="Source" /></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map(([name, value, source]) => (
            <TableRow key={name}>
              <TableCell>{name}</TableCell>
              <TableCell className={value === missing ? "text-amber-800" : "font-medium"}>{value}</TableCell>
              <TableCell className="text-slate-500">{source}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

type TimelineItem = { id: string; at: string; kind: string; title: string; body: string; extra?: React.ReactNode };

/** Nursing actions, events and notes in chronological order. */
export function Timeline({
  session,
  renderAction,
  renderEvent,
}: {
  session: SessionDetail;
  renderAction?: (action: NursingAction) => React.ReactNode;
  renderEvent?: (event: SessionEvent) => React.ReactNode;
}) {
  const items: TimelineItem[] = [
    ...session.nursing_actions.map((a: NursingAction) => ({
      id: a.id,
      at: a.performed_at,
      kind: tr("Action"),
      title: `${label(a.action_type)} · ${a.author_name}${a.amends ? ` ${tr("(amendment)")}` : ""}`,
      body: `${a.description} — ${a.reason ? `${tr("Reason:")} ${a.reason}` : tr("No reason documented")}`,
      extra: renderAction?.(a),
    })),
    ...session.events.map((e: SessionEvent) => ({
      id: e.id,
      at: e.occurred_at,
      kind: tr("Event"),
      title: label(e.event_type),
      body: `${e.description} — ${e.resolved_at ? `${tr("Resolved:")} ${e.resolution}` : tr("No resolution documented")}`,
      extra: renderEvent?.(e),
    })),
    ...session.nursing_notes.map((n: NursingNote) => ({
      id: n.id,
      at: n.created_at,
      kind: tr("Note"),
      title: n.author_name,
      body: n.text,
    })),
  ].sort((a, b) => a.at.localeCompare(b.at));
  useLocale();
  if (items.length === 0) return <p className="text-sm text-slate-500"><Tx k="No nursing documentation yet." /></p>;
  return (
    <ol className="space-y-3">
      {items.map((item) => (
        <li key={item.id} className="rounded border bg-white p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline">{item.kind}</Badge>
            <span className="font-medium">{item.title}</span>
            <time className="ms-auto text-slate-500">{dateTime(item.at)}</time>
          </div>
          <p className="mt-1 text-sm" dir="auto">
            {item.body}
          </p>
          {item.extra}
        </li>
      ))}
    </ol>
  );
}

export function NotificationInbox() {
  const inbox = useList<Notification>("/notifications/");
  const action = useAction();
  const unread = inbox.data?.filter((n) => !n.read_at).length ?? 0;
  useLocale();
  return (
    <Section
      title={`${tr("Notifications")}${unread ? ` (${unread} ${tr("unread")})` : ""}`}
      action={
        unread > 0 && (
          <Button
            variant="outline"
            size="sm"
            disabled={action.pending}
            onClick={async () => (await action.run(() => api.post("/notifications/read-all/"))) && inbox.reload()}
          >
            <Tx k="Mark all read" />
          </Button>
        )
      }
    >
      <Load from={inbox} empty="No notifications.">
        {(items) => (
          <ul className="divide-y text-sm">
            {items.slice(0, 12).map((n) => (
              <li key={n.id} className={`flex flex-wrap gap-2 py-2 ${n.read_at ? "text-slate-500" : "font-medium"}`}>
                <span>{tr(n.title)}</span>
                <time className="ms-auto text-slate-500">{dateTime(n.created_at)}</time>
              </li>
            ))}
          </ul>
        )}
      </Load>
      <ErrorNote message={action.error} />
    </Section>
  );
}

/** Laboratory values over time, one analyte at a time, with unit and reference range. */
export function LabTrends({ reports }: { reports: LabReport[] }) {
  const analytes = useMemo(() => [...new Set(reports.flatMap((r) => r.results.map((x) => x.analyte)))].sort(), [reports]);
  const [chosen, setChosen] = useState<string | null>(null);
  useLocale();
  const analyte = chosen ?? analytes[0];
  const points = reports
    .flatMap((r) => r.results.filter((x) => x.analyte === analyte).map((x) => ({ report: r, result: x })))
    .sort((a, b) => a.report.collected_at.localeCompare(b.report.collected_at));
  if (points.length === 0) return <p className="text-sm text-slate-500"><Tx k="No laboratory results available." /></p>;
  const { unit, reference_low: low, reference_high: high } = points[0].result;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Label htmlFor="analyte"><Tx k="Analyte" /></Label>
        <select
          id="analyte"
          className="rounded-md border px-2 py-1"
          value={analyte}
          onChange={(e) => setChosen(e.target.value)}
        >
          {analytes.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
        <span className="text-slate-500">
          {tr("Unit:")} {unit}
          {low && high ? ` · ${tr("Laboratory reference range")} ${Number(low)}–${Number(high)} ${unit}` : ""}
        </span>
      </div>
      <div className="h-56 w-full" role="img" aria-label={`${analyte} trend in ${unit}`}>
        <ResponsiveContainer>
          <LineChart
            data={points.map((p) => ({ date: dateOnly(p.report.collected_at), value: Number(p.result.value) }))}
            margin={{ left: 0, right: 16, top: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={12} />
            <YAxis domain={["auto", "auto"]} fontSize={12} unit={` ${unit}`} width={90} />
            <Tooltip formatter={(value) => [`${value} ${unit}`, analyte]} />
            <Line type="linear" dataKey="value" stroke="#0f766e" strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead><Tx k="Collected" /></TableHead>
            <TableHead>{analyte}</TableHead>
            <TableHead><Tx k="Released to patient" /></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {points.map((p) => (
            <TableRow key={p.result.id}>
              <TableCell>{dateOnly(p.report.collected_at)}</TableCell>
              <TableCell>{withUnit(p.result.value, p.result.unit)}</TableCell>
              <TableCell>{tr(p.report.released_to_patient ? "Yes" : "No")}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  CircleAlert,
  ClipboardCheck,
  Languages,
  LogOut,
  type LucideIcon,
  Sparkles,
  StickyNote,
  TriangleAlert,
  UserRound,
} from "lucide-react";
import { useMemo, useState, useSyncExternalStore } from "react";
import { type FieldValues, useForm } from "react-hook-form";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";

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
import { HOME, useAuth } from "@/lib/auth";
import { dateOnly, dateTime, label, minutesBetween, timeOnly, withUnit } from "@/lib/format";
import { setLocale, tr, Tx, useLocale } from "@/lib/i18n";
import { type Loaded, useAction, useList } from "@/lib/hooks";
import { notificationHref } from "@/lib/notifications";

// ---------------------------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------------------------

const ROLE_NAME: Record<string, string> = {
  doctor: "Doctor",
  nurse: "Nurse",
  patient: "Patient",
  family: "Family caregiver",
  dietitian: "Renal dietitian",
};
const ROLE_AREA: Record<string, string> = {
  doctor: "Physician workspace",
  nurse: "Nursing workspace",
  patient: "Patient companion",
  family: "Family access",
  dietitian: "Nutrition workspace",
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
  const current = (nav.find((item) => item.href === hash) ?? nav.find((item) => item.href === pathname) ?? nav[0])?.href;
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
            <span className="block text-lg leading-tight font-semibold text-brand-strong">{tr("Kulya")}</span>
            {user && <span className="micro block text-ink-3">{tr(ROLE_AREA[user.role] ?? "")}</span>}
          </span>
        </Link>
        <p className="mx-4 mb-4 flex items-center gap-2 rounded-md bg-chrome px-3 py-2 text-xs text-ink-2">
          <span className="size-2 shrink-0 rounded-full bg-jade" aria-hidden />
          {tr("Synthetic demonstration data")}
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
            <Link href="/" className="flex items-center gap-2 font-semibold text-brand-strong lg:hidden">
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
            <nav aria-label={tr("Sections")} className="flex gap-2 overflow-x-auto border-t border-line px-4 py-2 lg:hidden">
              {nav.map((item) => link(item, true))}
            </nav>
          )}
        </header>
        <main className="mx-auto w-full max-w-[1400px] space-y-5 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

type Tone = "default" | "ok" | "warn" | "bad" | "ai";
const TONE_TEXT: Record<Tone, string> = {
  default: "text-ink",
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  ai: "text-ai-ink",
};

export interface Stat {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: Tone;
  icon?: LucideIcon;
}

/** Row of key figures: micro-label on top, one large value, a short hint. Real data only. */
export function Stats({ items }: { items: Stat[] }) {
  useLocale();
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map(({ label: name, value, hint, tone = "default", icon: Icon }) => (
        <div key={name} className="rounded-lg border border-line bg-white p-4 shadow-[0_1px_3px_0_rgb(23_43_58/0.04)]">
          <div className="flex items-center justify-between gap-2">
            <span className="micro text-ink-2">{tr(name)}</span>
            {Icon && <Icon className="size-4 text-ink-3" aria-hidden />}
          </div>
          <p className={`mt-2 text-3xl leading-9 font-semibold ${TONE_TEXT[tone]}`}>{value}</p>
          {hint && <p className="mt-1 text-sm text-ink-3">{tr(hint)}</p>}
        </div>
      ))}
    </div>
  );
}

export function Section({
  id,
  icon: Icon,
  title,
  description,
  action,
  tone,
  className = "",
  children,
}: {
  id?: string;
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  /** "ai" marks content written by the model: periwinkle accent on the leading edge. */
  tone?: "ai";
  className?: string;
  children: React.ReactNode;
}) {
  const ai = tone === "ai";
  return (
    <Card id={id} className={`${ai ? "border-s-4! border-s-ai!" : ""} ${className}`}>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {Icon && (
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded-md ${ai ? "bg-ai-soft text-ai-ink" : "bg-brand-soft text-brand"}`}
            >
              <Icon className="size-4" aria-hidden />
            </span>
          )}
          <div>
            <CardTitle>
              <h2 className="text-base font-semibold text-ink">{tr(title)}</h2>
            </CardTitle>
            {description && <CardDescription className="mt-0.5 text-[13px] text-ink-2">{tr(description)}</CardDescription>}
          </div>
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
  if (from.loading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <p className="text-sm text-ink-3">
          <Tx k="Loading…" />
        </p>
        <div className="h-3 w-2/3 animate-pulse rounded bg-chrome" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-chrome" />
      </div>
    );
  }
  if (from.error) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-bad/25 bg-bad-soft px-3 py-2 text-sm text-bad">
        <CircleAlert className="size-4 shrink-0" aria-hidden />
        <span>{tr(from.error)}</span>
        <Button variant="outline" size="sm" className="ms-auto" onClick={from.reload}>
          <Tx k="Retry" />
        </Button>
      </div>
    );
  }
  if (from.data === null || (Array.isArray(from.data) && from.data.length === 0)) {
    return (
      <p className="rounded-md border border-dashed border-line bg-canvas px-3 py-4 text-center text-sm text-ink-3">
        {tr(empty ?? "Nothing to show yet.")}
      </p>
    );
  }
  return <>{children(from.data)}</>;
}

/** Switches between Arabic (right-to-left, default) and English. */
export function LanguageToggle() {
  const locale = useLocale();
  return (
    <Button variant="ghost" size="sm" onClick={() => setLocale(locale === "ar" ? "en" : "ar")}>
      <Languages className="size-4" aria-hidden />
      {locale === "ar" ? tr("English") : "العربية"}
    </Button>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="flex items-center gap-2 text-sm text-bad">
      <CircleAlert className="size-4 shrink-0" aria-hidden />
      {tr(message)}
    </p>
  ) : null;
}

// Clinical status badges: compact, square-cornered, colour by meaning (never colour alone: the
// text always states the status).
const OK = "border-ok/20 bg-ok-soft text-ok";
const WARN = "border-warn/25 bg-warn-soft text-warn";
const BAD = "border-bad/25 bg-bad-soft text-bad";
const INFO = "border-ai-ink/20 bg-ai-soft text-ai-ink";
const NEUTRAL = "border-line bg-chrome text-ink-2";
const STATUS_STYLE: Record<string, string> = {
  scheduled: NEUTRAL,
  in_progress: INFO,
  completed: OK,
  pending_review: WARN,
  unverified: WARN,
  open: WARN,
  processing: NEUTRAL,
  not_released: NEUTRAL,
  ai_unavailable: BAD,
  rejected: BAD,
  cancelled: BAD,
  verified: OK,
  reviewed: OK,
  released: OK,
  confirmed: OK,
  approved: OK,
  compatible: OK,
  needs_review: WARN,
  pending: WARN,
  check_portion: WARN,
  needs_dietitian_review: WARN,
  draft: NEUTRAL,
  general: NEUTRAL,
};

export function Status({ value }: { value: string }) {
  useLocale();
  return (
    <span
      className={`micro inline-flex min-h-5 items-center rounded border px-1.5 whitespace-nowrap ${STATUS_STYLE[value] ?? NEUTRAL}`}
    >
      {label(value)}
    </span>
  );
}

/** Every piece of AI-written content sits under this dashed "unverified draft" banner. */
export function AiLabel({ text }: { text: string }) {
  return (
    <p
      className="flex items-start gap-2 rounded-md border border-dashed border-ai bg-ai-soft px-3 py-2 text-sm text-ai-ink"
      data-testid="ai-label"
    >
      <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        <strong>
          <Tx k="AI-generated." />
        </strong>{" "}
        {tr(text.replace(/^AI-generated draft\.\s*/, ""))}
      </span>
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
  const control = "control w-full px-3";
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
            {field.hint && <p className="text-xs text-ink-3">{tr(field.hint)}</p>}
            {typeof error === "string" && (
              <p role="alert" className="text-xs text-bad">
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
              <TableCell>{tr(s.patient_name ?? "")}</TableCell>
              <TableCell>
                <Status value={s.status} />
              </TableCell>
              <TableCell>{withUnit(minutesBetween(s.started_at, s.ended_at), "min")}</TableCell>
              <TableCell className="text-end">
                {hrefFor && (
                  <Link className="font-medium text-brand hover:underline" href={hrefFor(s)}>
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

/** One figure in a metric tray: micro-label, large tabular value with its unit, provenance. */
function Metric({ name, value, source, missing }: { name: string; value: string; source: string; missing: boolean }) {
  return (
    <div className={`rounded-md border p-3 ${missing ? "border-warn/25 bg-warn-soft" : "border-line bg-chrome"}`}>
      <p className="micro text-ink-2">{name}</p>
      <p className={`mt-1 text-xl leading-7 font-semibold ${missing ? "text-warn" : "text-ink"}`}>{value}</p>
      <p className="text-xs text-ink-3">{source}</p>
    </div>
  );
}

/**
 * Session measurements. Headline figures sit in a metric tray; every vital sign and machine
 * reading follows in a table. A missing value is shown as missing (amber), never as zero.
 */
export function Measurements({ session }: { session: SessionDetail }) {
  useLocale();
  const missing = tr("Not recorded");
  const headline: [string, string, string][] = [
    [tr("Prescribed duration"), withUnit(session.prescribed_duration_minutes, "min"), tr("prescribed")],
    [tr("Documented duration"), withUnit(minutesBetween(session.started_at, session.ended_at), "min"), tr("calculated")],
    [tr("Pre-treatment weight"), withUnit(session.pre_weight_kg, "kg"), tr("measured")],
    [tr("Post-treatment weight"), withUnit(session.post_weight_kg, "kg"), tr("measured")],
    [tr("Ultrafiltration volume"), withUnit(session.uf_volume_ml, "mL"), tr("measured")],
  ];
  const rows: [string, string, string, string][] = [
    ...session.vitals.map((v: Vital): [string, string, string, string] => [
      v.id,
      `${label(v.kind)} (${tr(v.phase)}, ${timeOnly(v.recorded_at)})`,
      withUnit(v.value, v.unit),
      label(v.source),
    ]),
    ...session.device_readings.map((r: DeviceReading): [string, string, string, string] => [
      r.id,
      `${label(r.kind)} (${timeOnly(r.recorded_at)})`,
      withUnit(r.value, r.unit),
      label(r.source),
    ]),
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {headline.map(([name, value, source]) => (
          <Metric key={name} name={name} value={value} source={source} missing={value === missing} />
        ))}
      </div>
      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <Tx k="Measurement" />
                </TableHead>
                <TableHead>
                  <Tx k="Value" />
                </TableHead>
                <TableHead>
                  <Tx k="Source" />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(([id, name, value, source]) => (
                <TableRow key={id}>
                  <TableCell>{name}</TableCell>
                  <TableCell className="font-semibold">{value}</TableCell>
                  <TableCell className="text-ink-3">{source}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

type TimelineItem = {
  id: string;
  at: string;
  kind: string;
  tone: string;
  icon: LucideIcon;
  title: string;
  body: string;
  flag?: boolean;
  extra?: React.ReactNode;
};

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
      tone: "bg-brand-soft text-brand",
      icon: ClipboardCheck,
      title: `${label(a.action_type)} · ${tr(a.author_name)}${a.amends ? ` ${tr("(amendment)")}` : ""}`,
      body: `${tr(a.description)} — ${a.reason ? `${tr("Reason:")} ${tr(a.reason)}` : tr("No reason documented")}`,
      flag: !a.reason,
      extra: renderAction?.(a),
    })),
    ...session.events.map((e: SessionEvent) => ({
      id: e.id,
      at: e.occurred_at,
      kind: tr("Event"),
      tone: "bg-warn-soft text-warn",
      icon: TriangleAlert,
      title: label(e.event_type),
      body: `${tr(e.description)} — ${e.resolved_at ? `${tr("Resolved:")} ${tr(e.resolution)}` : tr("No resolution documented")}`,
      flag: !e.resolved_at,
      extra: renderEvent?.(e),
    })),
    ...session.nursing_notes.map((n: NursingNote) => ({
      id: n.id,
      at: n.created_at,
      kind: tr("Note"),
      tone: "bg-chrome text-ink-2",
      icon: StickyNote,
      title: tr(n.author_name),
      body: tr(n.text),
    })),
  ].sort((a, b) => a.at.localeCompare(b.at));
  useLocale();
  if (items.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-line bg-canvas px-3 py-4 text-center text-sm text-ink-3">
        <Tx k="No nursing documentation yet." />
      </p>
    );
  }
  return (
    <ol className="space-y-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <li key={item.id} className={`flex gap-3 rounded-md border p-3 ${item.flag ? "border-warn/30" : "border-line"}`}>
            <span className={`flex size-8 shrink-0 items-center justify-center rounded-md ${item.tone}`}>
              <Icon className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="micro rounded border border-line bg-white px-1.5 text-ink-2">{item.kind}</span>
                <span className="font-semibold">{item.title}</span>
                <time className="ms-auto text-xs text-ink-3">{dateTime(item.at)}</time>
              </div>
              <p className="mt-1 text-sm leading-6 text-ink" dir="auto">
                {item.body}
              </p>
              {item.extra}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function NotificationInbox({ className }: { className?: string }) {
  const { user } = useAuth();
  const inbox = useList<Notification>("/notifications/");
  const action = useAction();
  const unread = inbox.data?.filter((n) => !n.read_at).length ?? 0;
  useLocale();
  return (
    <Section
      id="notifications"
      icon={Bell}
      className={className}
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
          <ul className="divide-y divide-line text-sm">
            {items.slice(0, 6).map((n) => {
              const href = user ? notificationHref(n, user.role) : null;
              const content = <><span>{tr(n.title)}</span><time className="ms-auto text-ink-3">{dateTime(n.created_at)}</time></>;
              return (
                <li key={n.id} className={n.read_at ? "text-ink-3" : "font-medium"}>
                  {href ? (
                    <Link href={href} className="flex flex-wrap gap-2 rounded-md py-2 hover:bg-brand-soft hover:text-brand focus-visible:outline-2 focus-visible:outline-brand" onClick={() => {
                      if (!n.read_at) void action.run(() => api.post(`/notifications/${n.id}/read/`)).then(ok => { if (ok) inbox.reload(); });
                    }}>{content}</Link>
                  ) : <div className="flex flex-wrap gap-2 py-2">{content}</div>}
                </li>
              );
            })}
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
  if (points.length === 0) return <p className="text-sm text-ink-3"><Tx k="No laboratory results available." /></p>;
  const { unit, reference_low: low, reference_high: high } = points[0].result;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Label htmlFor="analyte"><Tx k="Analyte" /></Label>
        <select
          id="analyte"
          className="control px-2"
          value={analyte}
          onChange={(e) => setChosen(e.target.value)}
        >
          {analytes.map((name) => (
            <option key={name} value={name}>{tr(name)}</option>
          ))}
        </select>
        <span className="text-ink-3">
          {tr("Unit:")} {tr(unit)}
          {low && high ? ` · ${tr("Laboratory reference range")} ${Number(low)}–${Number(high)} ${tr(unit)}` : ""}
        </span>
      </div>
      <div className="h-56 w-full" dir="ltr" role="img" aria-label={`${tr(analyte)} ${tr("trend in")} ${tr(unit)}`}>
        <ResponsiveContainer>
          <LineChart
            data={points.map((p) => ({ date: dateOnly(p.report.collected_at), value: Number(p.result.value) }))}
            margin={{ left: 0, right: 16, top: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={12} />
            <YAxis domain={["auto", "auto"]} fontSize={12} width={48} />
            <Tooltip formatter={(value) => [`${value} ${tr(unit)}`, tr(analyte)]} />
            <Line type="linear" dataKey="value" stroke="#176b87" strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead><Tx k="Collected" /></TableHead>
            <TableHead>{tr(analyte)}</TableHead>
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

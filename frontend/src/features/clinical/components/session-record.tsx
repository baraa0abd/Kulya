"use client";

import { Status } from "@/components/feedback";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { dateTime, label, minutesBetween, timeOnly, withUnit } from "@/lib/format";
import { tr, Tx, useLocale } from "@/lib/i18n";
import {
  type DeviceReading,
  type NursingAction,
  type NursingNote,
  type Session,
  type SessionDetail,
  type SessionEvent,
  type Vital,
} from "@/lib/types";
import { ClipboardCheck, type LucideIcon, StickyNote, TriangleAlert } from "lucide-react";
import Link from "next/link";
export function SessionTable({
  sessions,
  hrefFor,
}: {
  sessions: Session[];
  hrefFor?: (s: Session) => string;
}) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <Tx k="Date" />
            </TableHead>
            <TableHead>
              <Tx k="Patient" />
            </TableHead>
            <TableHead>
              <Tx k="Status" />
            </TableHead>
            <TableHead>
              <Tx k="Documented duration" />
            </TableHead>
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
function Metric({
  name,
  value,
  source,
  missing,
}: {
  name: string;
  value: string;
  source: string;
  missing: boolean;
}) {
  return (
    <div
      className={`rounded-md border p-3 ${missing ? "border-warn/25 bg-warn-soft" : "border-line bg-chrome"}`}
    >
      <p className="micro text-ink-2">{name}</p>
      <p className={`mt-1 text-xl leading-7 font-semibold ${missing ? "text-warn" : "text-ink"}`}>
        {value}
      </p>
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
    [
      tr("Prescribed duration"),
      withUnit(session.prescribed_duration_minutes, "min"),
      tr("prescribed"),
    ],
    [
      tr("Documented duration"),
      withUnit(minutesBetween(session.started_at, session.ended_at), "min"),
      tr("calculated"),
    ],
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
          <Metric
            key={name}
            name={name}
            value={value}
            source={source}
            missing={value === missing}
          />
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
          <li
            key={item.id}
            className={`flex gap-3 rounded-md border p-3 ${item.flag ? "border-warn/30" : "border-line"}`}
          >
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded-md ${item.tone}`}
            >
              <Icon className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="micro rounded border border-line bg-white px-1.5 text-ink-2">
                  {item.kind}
                </span>
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

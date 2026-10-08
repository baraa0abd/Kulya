"use client";

import { Activity, Bell, ClipboardList, Users } from "lucide-react";
import Link from "next/link";

import { Load, Section, Stats, Status } from "@/components/feedback";
import { type NavItem, Shell } from "@/components/layout/shell";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { NotificationInbox } from "@/features/notifications/components/inbox";
import { useRole } from "@/lib/auth";
import { dateTime, label } from "@/lib/format";
import { useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type NursingAction, type Patient, type ReviewTask } from "@/lib/types";

const NAV: NavItem[] = [
  { href: "#reviews", label: "Pending physician reviews", icon: ClipboardList },
  { href: "#patients", label: "Assigned patients", icon: Users },
  { href: "#activity", label: "Recent nursing activity", icon: Activity },
  { href: "#notifications", label: "Notifications", icon: Bell },
];
const count = (rows: unknown[] | null) => (rows ? rows.length : "—");

export default function DoctorDashboard() {
  useLocale();
  const user = useRole("doctor");
  const patients = useList<Patient>(user ? "/patients/" : null);
  const tasks = useList<ReviewTask>(user ? "/doctor/review-tasks/?status=open" : null);
  const activity = useList<NursingAction>(user ? "/nursing-actions/?ordering=-created_at" : null);
  if (!user) return null;
  return (
    <Shell title="Doctor dashboard" nav={NAV}>
      <Stats
        items={[
          {
            label: "Reviews waiting",
            value: count(tasks.data),
            hint: "Need your review",
            tone: tasks.data?.length ? "warn" : "ok",
            icon: ClipboardList,
          },
          {
            label: "Findings to review",
            value: tasks.data ? tasks.data.reduce((sum, t) => sum + t.finding_count, 0) : "—",
            hint: "Across open reviews",
          },
          {
            label: "Assigned patients",
            value: count(patients.data),
            hint: "On your care team",
            icon: Users,
          },
          {
            label: "Recent nursing actions",
            value: count(activity.data),
            hint: "Latest entries",
            icon: Activity,
          },
        ]}
      />
      <div className="grid gap-5 xl:grid-cols-3 xl:items-start">
        <div className="space-y-5 xl:col-span-2">
          <Section
            id="reviews"
            icon={ClipboardList}
            title="Pending physician reviews"
            description="Sessions with a documentation review waiting for you."
          >
            <Load from={tasks} empty="No reviews are waiting.">
              {(rows) => (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <Tx k="Session" />
                      </TableHead>
                      <TableHead>
                        <Tx k="Patient" />
                      </TableHead>
                      <TableHead>
                        <Tx k="Findings" />
                      </TableHead>
                      <TableHead>
                        <Tx k="AI review" />
                      </TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((task) => (
                      <TableRow key={task.id}>
                        <TableCell>{dateTime(task.session_date)}</TableCell>
                        <TableCell>{tr(task.patient_name ?? "")}</TableCell>
                        <TableCell>{task.finding_count}</TableCell>
                        <TableCell>
                          <Status value={task.review_status ?? "processing"} />
                        </TableCell>
                        <TableCell className="text-end">
                          <Link
                            className="font-medium text-brand hover:underline"
                            href={`/doctor/sessions/${task.session}/`}
                          >
                            <Tx k="Review" />
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
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
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <Tx k="Record no." />
                      </TableHead>
                      <TableHead>
                        <Tx k="Name" />
                      </TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell>{p.mrn}</TableCell>
                        <TableCell>{tr(p.full_name ?? "")}</TableCell>
                        <TableCell className="text-end">
                          <Link
                            className="font-medium text-brand hover:underline"
                            href={`/doctor/patients/${p.id}/`}
                          >
                            <Tx k="History and labs" />
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Load>
          </Section>
        </div>
        <aside className="space-y-5">
          <Section
            id="activity"
            icon={Activity}
            title="Recent nursing activity"
            description="Latest nursing actions for your patients."
          >
            <Load from={activity} empty="No nursing actions recorded yet.">
              {(rows) => (
                <ul className="divide-y divide-line text-sm">
                  {rows.slice(0, 5).map((a) => (
                    <li key={a.id} className="py-2">
                      <div className="flex flex-wrap gap-2">
                        <span className="font-medium">{label(a.action_type)}</span>
                        <span className="text-ink-3">{tr(a.author_name ?? "")}</span>
                        <time className="ms-auto text-ink-3">{dateTime(a.performed_at)}</time>
                      </div>
                      <p dir="auto">{tr(a.description ?? "")}</p>
                      <Link
                        className="font-medium text-brand hover:underline"
                        href={`/doctor/sessions/${a.session}/`}
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

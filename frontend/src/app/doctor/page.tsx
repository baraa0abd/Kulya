"use client";

import Link from "next/link";

import { Load, NotificationInbox, Section, Shell, Status } from "@/components/app";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { NursingAction, Patient, ReviewTask } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { dateTime, label } from "@/lib/format";
import { useList } from "@/lib/hooks";

export default function DoctorDashboard() {
  const user = useRole("doctor");
  const patients = useList<Patient>(user ? "/patients/" : null);
  const tasks = useList<ReviewTask>(user ? "/doctor/review-tasks/?status=open" : null);
  const activity = useList<NursingAction>(user ? "/nursing-actions/?ordering=-created_at" : null);
  if (!user) return null;
  return (
    <Shell title="Doctor dashboard">
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Pending physician reviews" description="Sessions with a documentation review waiting for you.">
          <Load from={tasks} empty="No reviews are waiting.">
            {(rows) => (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Session</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>Findings</TableHead>
                    <TableHead>AI review</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((task) => (
                    <TableRow key={task.id}>
                      <TableCell>{dateTime(task.session_date)}</TableCell>
                      <TableCell>{task.patient_name}</TableCell>
                      <TableCell>{task.finding_count}</TableCell>
                      <TableCell>
                        <Status value={task.review_status ?? "processing"} />
                      </TableCell>
                      <TableCell className="text-right">
                        <Link className="text-teal-800 underline" href={`/doctor/sessions/${task.session}/`}>
                          Review
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Load>
        </Section>

        <Section title="Assigned patients" description="Only patients on your care team are listed.">
          <Load from={patients} empty="No patients are assigned to you.">
            {(rows) => (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Record no.</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell>{p.mrn}</TableCell>
                      <TableCell>{p.full_name}</TableCell>
                      <TableCell className="text-right">
                        <Link className="text-teal-800 underline" href={`/doctor/patients/${p.id}/`}>
                          History and labs
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Load>
        </Section>

        <Section title="Recent nursing activity" description="Latest nursing actions for your patients.">
          <Load from={activity} empty="No nursing actions recorded yet.">
            {(rows) => (
              <ul className="divide-y text-sm">
                {rows.slice(0, 8).map((a) => (
                  <li key={a.id} className="py-2">
                    <div className="flex flex-wrap gap-2">
                      <span className="font-medium">{label(a.action_type)}</span>
                      <span className="text-slate-500">{a.author_name}</span>
                      <time className="ml-auto text-slate-500">{dateTime(a.performed_at)}</time>
                    </div>
                    <p dir="auto">{a.description}</p>
                    <Link className="text-teal-800 underline" href={`/doctor/sessions/${a.session}/`}>
                      Open session
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Load>
        </Section>

        <NotificationInbox />
      </div>
    </Shell>
  );
}

"use client";

import { Bell, ClipboardList, FileText, Salad, Stethoscope, Users } from "lucide-react";
import Link from "next/link";

import { Load, Section, Stats } from "@/components/feedback";
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
import { type NutritionRow } from "@/features/nutrition/types";
import { useRole } from "@/lib/auth";
import { useGet } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";

const NAV: NavItem[] = [
  { href: "#patients", label: "Assigned patients", icon: Users },
  { href: "#notifications", label: "Notifications", icon: Bell },
];

export default function DietitianDashboard() {
  useLocale();
  const user = useRole("dietitian");
  const rows = useGet<NutritionRow[]>(user ? "/nutrition/overview/" : null);
  if (!user) return null;
  const total = (pick: (row: NutritionRow) => number | undefined) =>
    rows.data ? rows.data.reduce((sum, row) => sum + (pick(row) ?? 0), 0) : "—";
  const waiting = total((r) => r.pending_recommendations);
  return (
    <Shell title="Dietitian dashboard" nav={NAV}>
      <Stats
        items={[
          {
            label: "Assigned patients",
            value: rows.data ? rows.data.length : "—",
            hint: "On your care team",
            icon: Users,
          },
          {
            label: "Meal ideas to review",
            value: waiting,
            tone: waiting ? "warn" : "ok",
            icon: Salad,
          },
          {
            label: "Report drafts",
            value: total((r) => r.draft_reports),
            hint: "Not yet released",
            icon: FileText,
          },
          { label: "Nurse referrals", value: total((r) => r.referrals), icon: Stethoscope },
        ]}
      />
      <Section
        id="patients"
        icon={ClipboardList}
        title="Assigned patients"
        description="Open a patient to review the diary, approve a plan, and review AI drafts."
      >
        <Load from={rows} empty="No patients are assigned to you.">
          {(data) => (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      <Tx k="Patient" />
                    </TableHead>
                    <TableHead>
                      <Tx k="Nutrition plan" />
                    </TableHead>
                    <TableHead>
                      <Tx k="Days recorded" />
                    </TableHead>
                    <TableHead>
                      <Tx k="Meal ideas to review" />
                    </TableHead>
                    <TableHead>
                      <Tx k="Report drafts" />
                    </TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.map((row) => (
                    <TableRow key={row.patient}>
                      <TableCell className="font-medium">{tr(row.patient_name ?? "")}</TableCell>
                      <TableCell className={row.has_active_plan ? "text-ok" : "text-warn"}>
                        {row.has_active_plan ? tr("Approved") : tr("None yet")}
                      </TableCell>
                      <TableCell>{row.days_recorded_last_7} / 7</TableCell>
                      <TableCell>{row.pending_recommendations ?? 0}</TableCell>
                      <TableCell>{row.draft_reports ?? 0}</TableCell>
                      <TableCell>
                        <Link
                          href={`/doctor/patients/${row.patient}/nutrition/`}
                          className="font-medium text-brand hover:underline"
                        >
                          <Tx k="Open nutrition review" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </Load>
      </Section>
      <NotificationInbox />
    </Shell>
  );
}

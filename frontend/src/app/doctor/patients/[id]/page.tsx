"use client";

import { ClipboardList, FlaskConical, History, Salad } from "lucide-react";
import { useParams } from "next/navigation";
import { z } from "zod";

import { ErrorNote, Load, Section } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { type NavItem, Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { LabTrends } from "@/features/clinical/components/lab-trends";
import { SessionTable } from "@/features/clinical/components/session-record";
import { api } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { optionalNumber } from "@/lib/validation";
import { dateOnly, withUnit } from "@/lib/format";
import { useAction, useGet, useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type LabReport, type Patient, type Prescription, type Session } from "@/lib/types";

const orderSchema = z.object({
  duration_minutes: z.coerce
    .number()
    .int()
    .min(30, "At least 30 minutes.")
    .max(600, "At most 600 minutes."),
  target_uf_ml: optionalNumber(0, 10000),
  blood_flow_ml_min: optionalNumber(50, 600),
  access_type: z.enum(["AVF", "AVG", "CVC"]),
});

const SECTIONS: NavItem[] = [
  { href: "#history", label: "Dialysis session history", icon: History },
  { href: "#labs", label: "Laboratory trends", icon: FlaskConical },
  { href: "#orders", label: "Dialysis orders", icon: ClipboardList },
];

export default function DoctorPatientPage() {
  useLocale();
  const user = useRole("doctor");
  const { id } = useParams<{ id: string }>();
  const patient = useGet<Patient>(user ? `/patients/${id}/` : null);
  const sessions = useList<Session>(
    user ? `/sessions/?patient=${id}&ordering=-scheduled_start` : null,
  );
  const labs = useList<LabReport>(user ? `/labs/?patient=${id}` : null);
  const orders = useList<Prescription>(user ? `/prescriptions/?patient=${id}` : null);
  const release = useAction();
  if (!user) return null;
  const unreleased = labs.data?.filter((r) => !r.released_to_patient) ?? [];
  const NAV = [
    ...SECTIONS,
    { href: `/doctor/patients/${id}/nutrition/`, label: "Nutrition", icon: Salad },
  ];
  return (
    <Shell
      title={patient.data ? `${tr(patient.data.full_name)} (${patient.data.mrn})` : "Patient"}
      back="/doctor/"
      nav={NAV}
    >
      <Section id="history" icon={History} title="Dialysis session history">
        <Load from={sessions} empty="No sessions recorded.">
          {(rows) => <SessionTable sessions={rows} hrefFor={(s) => `/doctor/sessions/${s.id}/`} />}
        </Load>
      </Section>

      <Section
        id="labs"
        icon={FlaskConical}
        title="Laboratory trends"
        description="Values are shown exactly as reported by the laboratory, with their units."
      >
        <Load from={labs} empty="No laboratory reports.">
          {(rows) => <LabTrends reports={rows} />}
        </Load>
        {unreleased.length > 0 && (
          <div className="mt-4 space-y-2 text-sm">
            <p className="font-medium">
              <Tx k="Reports not yet released to the patient" />
            </p>
            {unreleased.map((report) => (
              <div key={report.id} className="flex flex-wrap items-center gap-3">
                <span>
                  {tr("Collected")} {dateOnly(report.collected_at)}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={release.pending}
                  onClick={async () =>
                    (await release.run(() => api.post(`/labs/${report.id}/release/`))) &&
                    labs.reload()
                  }
                >
                  <Tx k="Release to patient" />
                </Button>
              </div>
            ))}
            <ErrorNote message={release.error} />
          </div>
        )}
      </Section>

      <Section
        id="orders"
        icon={ClipboardList}
        title="Dialysis orders"
        description="A new order becomes the active version; earlier versions are kept."
      >
        <Load from={orders} empty="No dialysis order on file.">
          {(rows) => (
            <ul className="mb-4 space-y-1 text-sm">
              {rows.map((rx) => (
                <li key={rx.id} className={rx.active ? "font-medium" : "text-ink-3"}>
                  {tr("Version")} {rx.version}
                  {rx.active ? ` ${tr("(active)")}` : ""}: {withUnit(rx.duration_minutes, "min")} ·{" "}
                  {tr("target UF")} {withUnit(rx.target_uf_ml, "mL")} · {tr("blood flow")}{" "}
                  {withUnit(rx.blood_flow_ml_min, "mL/min")} · {tr("access")} {tr(rx.access_type)}
                </li>
              ))}
            </ul>
          )}
        </Load>
        <ZForm
          schema={orderSchema}
          submitLabel="Create new order version"
          fields={[
            { name: "duration_minutes", label: "Duration (min)", type: "number" },
            { name: "target_uf_ml", label: "Target UF (mL)", type: "number" },
            { name: "blood_flow_ml_min", label: "Blood flow (mL/min)", type: "number" },
            {
              name: "access_type",
              label: "Access",
              type: "select",
              options: [
                ["AVF", "AVF"],
                ["AVG", "AVG"],
                ["CVC", "CVC"],
              ],
            },
          ]}
          onSubmit={async (values) => {
            await api.post("/prescriptions/", { patient: id, ...values });
            orders.reload();
          }}
        />
      </Section>
    </Shell>
  );
}

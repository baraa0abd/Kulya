"use client";

import { ClipboardList, UserPlus, Users } from "lucide-react";
import { z } from "zod";

import { ErrorNote, Load, Section, Status } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { type NavItem, Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { dateOnly, label } from "@/lib/format";
import { useAction, useList } from "@/lib/hooks";
import { tr, useLocale } from "@/lib/i18n";
import { requiredText } from "@/lib/validation";

interface Account {
  id: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
}
interface RegisteredPatient {
  id: string;
  mrn: string;
  full_name: string;
  date_of_birth: string;
  account: string | null;
}
interface Assignment {
  id: string;
  patient: string;
  professional_name: string;
  professional_role: string;
  active: boolean;
}

const ROLES: [string, string][] = [
  ["nurse", "Nurse"],
  ["doctor", "Doctor"],
  ["dietitian", "Renal dietitian"],
  ["patient", "Patient"],
  ["family", "Family caregiver"],
];
const CARE_TEAM = ["nurse", "doctor", "dietitian"];

const accountSchema = z.object({
  username: requiredText("Username"),
  display_name: requiredText("Name"),
  role: z.string(),
  password: z.string().min(10, "Use at least 10 characters."),
});
const patientSchema = z.object({
  mrn: requiredText("Record no."),
  full_name: requiredText("Name"),
  date_of_birth: z.string().min(1, "Choose a date."),
  account: z.string(),
});
const teamSchema = z.object({
  patient: z.string().min(1, "Choose a patient."),
  professional: z.string().min(1, "Choose a professional."),
});

const NAV: NavItem[] = [
  { href: "#accounts", label: "Accounts", icon: UserPlus },
  { href: "#patients", label: "Patients", icon: Users },
  { href: "#teams", label: "Care teams", icon: ClipboardList },
];

/** The organization administrator opens accounts, registers patients and builds care teams.
 *  No clinical record is shown here. ponytail: lists show the first 50 rows; add paging past that. */
export default function ManagePage() {
  useLocale();
  const user = useRole("org_admin");
  const accounts = useList<Account>(user ? "/admin/accounts/" : null);
  const patients = useList<RegisteredPatient>(user ? "/admin/patients/" : null);
  const teams = useList<Assignment>(user ? "/care-assignments/" : null);
  const act = useAction();
  if (!user) return null;
  const staff = accounts.data?.filter((a) => a.is_active && CARE_TEAM.includes(a.role)) ?? [];
  const linked = new Set(patients.data?.map((p) => p.account));
  const free =
    accounts.data?.filter((a) => a.is_active && a.role === "patient" && !linked.has(a.username)) ??
    [];
  const nameOf = (id: string) => patients.data?.find((p) => p.id === id)?.full_name ?? "";
  const stop = async (path: string, reload: () => void) =>
    (await act.run(() => api.post(path))) && reload();
  return (
    <Shell title="Administration" nav={NAV}>
      <ErrorNote message={act.error} />
      <Section
        id="accounts"
        icon={UserPlus}
        title="Accounts"
        description="Give each person their own account and a first password. They change it after signing in."
      >
        <Load from={accounts} empty="No accounts yet.">
          {(rows) => (
            <ul className="mb-4 divide-y divide-line text-sm">
              {rows.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-3 py-2">
                  <span className="font-medium" dir="auto">
                    {a.display_name || a.username}
                  </span>
                  <span className="text-ink-3">{a.username}</span>
                  <span>{label(a.role)}</span>
                  {a.is_active ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="ms-auto"
                      disabled={act.pending}
                      onClick={() => stop(`/admin/accounts/${a.id}/deactivate/`, accounts.reload)}
                    >
                      {tr("Deactivate")}
                    </Button>
                  ) : (
                    <span className="ms-auto text-ink-3">{tr("Deactivated")}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Load>
        <ZForm
          schema={accountSchema}
          submitLabel="Create account"
          fields={[
            { name: "display_name", label: "Name" },
            { name: "username", label: "Username" },
            { name: "role", label: "Role", type: "select", options: ROLES },
            { name: "password", label: "First password", type: "password" },
          ]}
          onSubmit={async (values) => {
            await api.post("/admin/accounts/", values);
            accounts.reload();
          }}
        />
      </Section>

      <Section
        id="patients"
        icon={Users}
        title="Patients"
        description="Register the patient, then link their own account so they can sign in."
      >
        <Load from={patients} empty="No patients registered yet.">
          {(rows) => (
            <ul className="mb-4 divide-y divide-line text-sm">
              {rows.map((p) => (
                <li key={p.id} className="flex flex-wrap gap-3 py-2">
                  <span className="text-ink-3">{p.mrn}</span>
                  <span className="font-medium" dir="auto">
                    {p.full_name}
                  </span>
                  <span>{dateOnly(p.date_of_birth)}</span>
                  <span className="ms-auto text-ink-3">{p.account ?? tr("No account linked")}</span>
                </li>
              ))}
            </ul>
          )}
        </Load>
        <ZForm
          schema={patientSchema}
          submitLabel="Register patient"
          fields={[
            { name: "mrn", label: "Record no." },
            { name: "full_name", label: "Name" },
            { name: "date_of_birth", label: "Date of birth", type: "date" },
            {
              name: "account",
              label: "Patient account",
              type: "select",
              options: [
                ["", "No account yet"],
                ...free.map((a): [string, string] => [a.username, a.username]),
              ],
            },
          ]}
          onSubmit={async ({ account, ...values }) => {
            await api.post("/admin/patients/", { ...values, account: account || null });
            patients.reload();
          }}
        />
      </Section>

      <Section
        id="teams"
        icon={ClipboardList}
        title="Care teams"
        description="Staff see a patient only while they are on that patient's care team."
      >
        <Load from={teams} empty="No care teams yet.">
          {(rows) => (
            <ul className="mb-4 divide-y divide-line text-sm">
              {rows.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-3 py-2">
                  <span className="font-medium" dir="auto">
                    {nameOf(t.patient)}
                  </span>
                  <span dir="auto">{t.professional_name}</span>
                  <span className="text-ink-3">{label(t.professional_role)}</span>
                  {t.active ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="ms-auto"
                      disabled={act.pending}
                      onClick={() => stop(`/care-assignments/${t.id}/deactivate/`, teams.reload)}
                    >
                      {tr("Remove from team")}
                    </Button>
                  ) : (
                    <span className="ms-auto">
                      <Status value="ended" />
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Load>
        <ZForm
          schema={teamSchema}
          submitLabel="Add to care team"
          fields={[
            {
              name: "patient",
              label: "Patient",
              type: "select",
              options: (patients.data ?? []).map((p): [string, string] => [
                p.id,
                `${p.mrn} — ${p.full_name}`,
              ]),
            },
            {
              name: "professional",
              label: "Professional",
              type: "select",
              options: staff.map((a): [string, string] => [
                a.id,
                `${a.display_name || a.username} (${tr(label(a.role))})`,
              ]),
            },
          ]}
          onSubmit={async (values) => {
            await api.post("/care-assignments/", values);
            teams.reload();
          }}
        />
      </Section>
    </Shell>
  );
}

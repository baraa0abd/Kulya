"use client";

import { HeartPulse, Share2 } from "lucide-react";
import { z } from "zod";

import { ErrorNote, Load, Section } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { type NavItem, Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { dateOnly, dateTime, label, withUnit } from "@/lib/format";
import { useAction, useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type Consent, type Vital } from "@/lib/types";
import { requiredNumber, requiredText } from "@/lib/validation";

const HOME_UNITS: Record<string, string> = {
  weight: "kg",
  systolic_bp: "mmHg",
  diastolic_bp: "mmHg",
  heart_rate: "bpm",
};
const measurementSchema = z.object({ kind: z.string(), value: requiredNumber });
const consentSchema = z.object({
  caregiver_username: requiredText("Caregiver username"),
  share: z.enum([
    "summaries",
    "summaries,appointments",
    "summaries,appointments,labs",
    "summaries,appointments,labs,nutrition",
    "summaries,appointments,labs,nutrition,nutrition_log",
  ]),
});

const NAV: NavItem[] = [
  { href: "#sharing", label: "Family sharing", icon: Share2 },
  { href: "#home", label: "Home measurements", icon: HeartPulse },
];

function FamilySharing() {
  const grants = useList<Consent>("/consent/");
  const revoke = useAction();
  return (
    <Section
      id="sharing"
      icon={Share2}
      title="Family sharing"
      description="You decide what a family caregiver can see. You can stop sharing at any time."
    >
      <Load from={grants} empty="You are not sharing with anyone.">
        {(rows) => (
          <ul className="mb-4 divide-y divide-line text-sm">
            {rows.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-3 py-2">
                <span className="font-medium">{tr(c.caregiver_name ?? "")}</span>
                <span>{c.scopes.map(label).join(", ")}</span>
                {c.revoked_at ? (
                  <span className="text-ink-3">
                    {tr("Stopped")} {dateOnly(c.revoked_at)}
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    className="ms-auto"
                    disabled={revoke.pending}
                    onClick={async () =>
                      (await revoke.run(() => api.post(`/consent/${c.id}/revoke/`))) &&
                      grants.reload()
                    }
                  >
                    <Tx k="Stop sharing" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Load>
      <ErrorNote message={revoke.error} />
      <ZForm
        schema={consentSchema}
        submitLabel="Share with caregiver"
        fields={[
          { name: "caregiver_username", label: "Caregiver username" },
          {
            name: "share",
            label: "What to share",
            type: "select",
            options: [
              ["summaries", "Reviewed summaries"],
              ["summaries,appointments", "Summaries and appointments"],
              ["summaries,appointments,labs", "Summaries, appointments and released lab results"],
              ["summaries,appointments,labs,nutrition", "All of the above and my food diary"],
              [
                "summaries,appointments,labs,nutrition,nutrition_log",
                "All of the above, and they may record meals for me",
              ],
            ],
          },
        ]}
        onSubmit={async (values) => {
          await api.post("/consent/", {
            caregiver_username: values.caregiver_username,
            scopes: values.share.split(","),
          });
          grants.reload();
        }}
      />
    </Section>
  );
}

function HomeMeasurements() {
  const mine = useList<Vital>("/vitals/?ordering=-recorded_at");
  return (
    <Section
      id="home"
      icon={HeartPulse}
      title="Home measurements"
      description="Measurements you enter are marked as patient-reported for your care team."
    >
      <ZForm
        schema={measurementSchema}
        submitLabel="Submit measurement"
        fields={[
          {
            name: "kind",
            label: "Measurement",
            type: "select",
            options: Object.entries(HOME_UNITS).map(([kind, unit]): [string, string] => [
              kind,
              `${label(kind)} (${tr(unit)})`,
            ]),
          },
          { name: "value", label: "Value", type: "number" },
        ]}
        onSubmit={async (values) => {
          await api.post("/vitals/", {
            ...values,
            phase: "pre",
            recorded_at: new Date().toISOString(),
          });
          mine.reload();
        }}
      />
      <div className="mt-4">
        <Load from={mine} empty="You have not submitted any measurements.">
          {(rows) => (
            <ul className="divide-y divide-line text-sm">
              {rows.slice(0, 8).map((v) => (
                <li key={v.id} className="flex gap-3 py-2">
                  <span>{label(v.kind)}</span>
                  <span className="font-medium">{withUnit(v.value, v.unit)}</span>
                  <time className="ms-auto text-ink-3">{dateTime(v.recorded_at)}</time>
                </li>
              ))}
            </ul>
          )}
        </Load>
      </div>
    </Section>
  );
}

/** What only the patient manages: who in the family may see their record, and home readings. */
export default function PatientHome() {
  useLocale();
  const user = useRole("patient");
  if (!user) return null;
  return (
    <Shell title="Family and home" back="/patient/" nav={NAV}>
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <FamilySharing />
        <HomeMeasurements />
      </div>
    </Shell>
  );
}

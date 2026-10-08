"use client";

import { Load, Section } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { PlanCard } from "@/features/nutrition/components/common";
import { type NutritionObservation, type NutritionPlan } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { optionalNumber, requiredText } from "@/lib/validation";
import { dateOnly, label } from "@/lib/format";
import { useGet } from "@/lib/hooks";
import { tr } from "@/lib/i18n";
import { ClipboardList, Stethoscope } from "lucide-react";
import { z } from "zod";
export const limit = optionalNumber(1, 100000);

const planSchema = z.object({
  potassium_mg_max: limit,
  sodium_mg_max: limit,
  phosphorus_mg_max: limit,
  fluid_ml_max: limit,
  allergies: z.string().trim().max(400),
  guidance: z.string().trim().max(2000),
});

const words = (text: string) =>
  text
    .split(/[,،]/)
    .map((w) => w.trim())
    .filter(Boolean);

export function PlanPanel({ patient, canDecide }: { patient: string; canDecide: boolean }) {
  const path = `/nutrition/patients/${patient}/plans/`;
  const plans = useGet<NutritionPlan[]>(path);
  const active = plans.data?.find((plan) => plan.active);
  return (
    <Section
      id="plan"
      icon={ClipboardList}
      title="Nutrition plan"
      description="Only a doctor or dietitian approves a plan. Saving creates a new version; earlier versions are kept."
    >
      <Load from={plans} empty="No nutrition plan has been approved yet.">
        {(rows) => (
          <div className="mb-4 space-y-3">
            <PlanCard plan={rows.find((p) => p.active) ?? null} />
            <p className="text-xs text-ink-3">
              {tr("Versions on file")}: {rows.length}
            </p>
          </div>
        )}
      </Load>
      {canDecide && !plans.loading && (
        <ZForm
          key={active?.id ?? "new-plan"}
          defaults={{
            ...active?.prescribed_targets,
            guidance: active?.guidance ?? "",
            allergies: active?.allergies.map(tr).join("، ") ?? "",
          }}
          schema={planSchema}
          submitLabel="Approve new plan version"
          fields={[
            { name: "potassium_mg_max", label: "Potassium limit per meal (mg)", type: "number" },
            { name: "sodium_mg_max", label: "Sodium limit per meal (mg)", type: "number" },
            { name: "phosphorus_mg_max", label: "Phosphorus limit per meal (mg)", type: "number" },
            { name: "fluid_ml_max", label: "Fluid limit per meal (mL)", type: "number" },
            {
              name: "allergies",
              label: "Allergies (comma separated)",
              hint: "Recipes containing these are never suggested.",
            },
            { name: "guidance", label: "Guidance for the patient", type: "textarea" },
          ]}
          onSubmit={async ({ allergies, guidance, ...limits }) => {
            const targets = Object.fromEntries(
              Object.entries(limits).filter(([, v]) => v !== undefined),
            );
            await api.post(path, {
              prescribed_targets: targets,
              allergies: words(allergies),
              guidance,
            });
            plans.reload();
          }}
        />
      )}
    </Section>
  );
}

const observationSchema = z.object({
  kind: z.enum(["eating_difficulty", "nausea", "loss_of_appetite", "other"]),
  text: requiredText("Observation"),
  referred: z.enum(["no", "yes"]),
});

export function Observations({ patient, canWrite }: { patient: string; canWrite: boolean }) {
  const path = `/nutrition/patients/${patient}/observations/`;
  const notes = useGet<NutritionObservation[]>(path);
  return (
    <Section
      id="observations"
      icon={Stethoscope}
      title="Nursing observations about eating"
      description="A nurse records what the patient reports and can refer it to the doctor and dietitian."
    >
      <Load from={notes} empty="No observations recorded.">
        {(rows) => (
          <ul className="mb-4 divide-y divide-line text-sm">
            {rows.map((note) => (
              <li key={note.id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="font-medium">{label(note.kind)}</span>
                <span dir="auto">{tr(note.text ?? "")}</span>
                {note.referred && (
                  <span className="micro rounded border border-warn/25 bg-warn-soft px-1.5 text-warn">
                    {tr("Referred")}
                  </span>
                )}
                <span className="ms-auto text-ink-3">
                  {tr(note.author_name ?? "")} · {dateOnly(note.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Load>
      {canWrite && (
        <ZForm
          schema={observationSchema}
          submitLabel="Record observation"
          fields={[
            {
              name: "kind",
              label: "Observation",
              type: "select",
              options: ["eating_difficulty", "nausea", "loss_of_appetite", "other"].map(
                (k): [string, string] => [k, label(k)],
              ),
            },
            {
              name: "referred",
              label: "Refer to doctor and dietitian",
              type: "select",
              options: [
                ["no", "No"],
                ["yes", "Yes"],
              ],
            },
            { name: "text", label: "What was observed or reported", type: "textarea" },
          ]}
          onSubmit={async (values) => {
            await api.post(path, { ...values, referred: values.referred === "yes" });
            notes.reload();
          }}
        />
      )}
    </Section>
  );
}

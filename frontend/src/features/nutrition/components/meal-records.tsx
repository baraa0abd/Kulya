"use client";

import { Load, Section, Status } from "@/components/feedback";
import { unitName } from "@/features/nutrition/components/common";
import { type Meal } from "@/features/nutrition/types";
import { dateTime, label } from "@/lib/format";
import { useGet } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { type Patient } from "@/lib/types";
import { UtensilsCrossed } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

const SHOWN = 5;

/**
 * Dashboard card with the latest diary meals, the same for every role. Care-team roles pass their
 * patients and choose one; a patient passes none and sees their own diary.
 */
export function MealRecords({
  patients,
  diary,
  action,
  children,
}: {
  patients?: Patient[];
  diary: (patient: string) => string;
  action?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  const patient = patients ? (picked ?? patients[0]?.id ?? null) : "";
  const meals = useGet<Meal[]>(
    patient === null ? null : `/nutrition/meals/${patient ? `?patient=${patient}` : ""}`,
  );
  return (
    <Section
      id="meals"
      icon={UtensilsCrossed}
      title="Meal records"
      description="The latest meals in the food diary, as the patient recorded them."
      action={action}
    >
      {patients && patients.length > 1 && (
        <label className="mb-3 block text-sm">
          {tr("Patient")}
          <select
            className="control w-full px-3"
            value={patient ?? ""}
            onChange={(e) => setPicked(e.target.value)}
          >
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.mrn} — {tr(p.full_name)}
              </option>
            ))}
          </select>
        </label>
      )}
      {patient === null ? (
        <p className="text-sm text-ink-3">
          <Tx k="No patients are assigned to you." />
        </p>
      ) : (
        <>
          <Load from={meals} empty="No meals recorded in this period.">
            {(rows) => (
              <ul className="divide-y divide-line text-sm">
                {rows.slice(0, SHOWN).map((meal) => (
                  <li key={meal.id} className="py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">{label(meal.meal_type)}</span>
                      <Status value={meal.confirmation_status} />
                      <time className="ms-auto text-ink-3">{dateTime(meal.consumed_at)}</time>
                    </div>
                    <p dir="auto">
                      {meal.components
                        .map(
                          (c) =>
                            `${tr(c.food_name || c.name)} (${Number(c.quantity)} ${unitName(c.unit)})`,
                        )
                        .join(" · ")}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Load>
          <Link
            className="mt-3 inline-block text-sm font-medium text-brand hover:underline"
            href={diary(patient)}
          >
            <Tx k="Open the full meal diary" />
          </Link>
        </>
      )}
      {children}
    </Section>
  );
}

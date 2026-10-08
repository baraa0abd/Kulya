"use client";

import {
  type DiarySummary,
  NUTRIENT_KEYS,
  type NutrientKey,
  type Nutrients,
  type NutritionPlan,
} from "@/features/nutrition/types";
import { dateOnly, withUnit } from "@/lib/format";
import { getLocale, tr, Tx, useLocale } from "@/lib/i18n";
import { Info } from "lucide-react";
const NUTRIENT: Record<NutrientKey, [name: string, unit: string]> = {
  energy_kcal: ["Energy", "kcal"],
  protein_g: ["Protein", "g"],
  sodium_mg: ["Sodium", "mg"],
  potassium_mg: ["Potassium", "mg"],
  phosphorus_mg: ["Phosphorus", "mg"],
  calcium_mg: ["Calcium", "mg"],
  fluid_ml: ["Fluid", "mL"],
};

const UNIT_NAME: Record<string, string> = { g: "grams", ml: "millilitres" };

export const unitName = (unit: string) => tr(UNIT_NAME[unit] ?? unit);

export const localName = (names: Record<string, string>, fallback: string) =>
  names[getLocale()] ?? tr(fallback);

/** Shown wherever nutrient numbers or meal ideas appear. */
export function Disclaimer() {
  return (
    <p className="flex items-start gap-2 rounded-md border border-line bg-chrome px-3 py-2 text-sm text-ink-2">
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
      <Tx k="Estimates only, from a demonstration food list that has not been verified. This is not medical advice: ask your care team before changing what you eat." />
    </p>
  );
}

/** Nutrient figures with units. A value that is not available says so; it is never shown as 0. */
export function NutrientTray({
  values,
  dense = false,
  coverage,
}: {
  values: Nutrients | null;
  dense?: boolean;
  coverage?: Record<NutrientKey, number>;
}) {
  useLocale();
  return (
    <dl className={`grid grid-cols-2 gap-2 sm:grid-cols-4 ${dense ? "" : "xl:grid-cols-7"}`}>
      {NUTRIENT_KEYS.map((key) => {
        const value = values?.[key] ?? null;
        const [name, unit] = NUTRIENT[key];
        return (
          <div
            key={key}
            className={`rounded-md border p-2.5 ${value === null ? "border-warn/25 bg-warn-soft" : "border-line bg-chrome"}`}
          >
            <dt className="micro text-ink-2">{tr(name)}</dt>
            <dd
              className={`mt-0.5 font-semibold ${value === null ? "text-sm text-warn" : "text-lg text-ink"}`}
            >
              {value === null ? tr("Not available") : withUnit(value, unit)}
            </dd>
            {coverage && (
              <p className="mt-1 text-xs text-ink-3">
                {tr("Complete recorded days")}: {coverage[key]}
              </p>
            )}
          </div>
        );
      })}
    </dl>
  );
}

export function DiaryFacts({ summary }: { summary: DiarySummary }) {
  const missing = summary.days_in_period - summary.days_recorded;
  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-2">
        {tr("Daily average on days with complete records.")} {tr("Meals recorded on")}{" "}
        {summary.days_recorded} {tr("of")} {summary.days_in_period} {tr("days")}.
      </p>
      <NutrientTray
        values={summary.daily_average_on_complete_days}
        coverage={summary.days_with_complete_data}
      />
      {NUTRIENT_KEYS.some((key) => summary.daily_average_on_complete_days[key] === null) && (
        <p className="text-sm text-ink-3">
          {tr(
            "Missing nutrient values are not zero. Check food choices and portions in the diary.",
          )}
        </p>
      )}
      {missing > 0 && (
        <p className="rounded-md border border-warn/25 bg-warn-soft px-3 py-2 text-sm text-warn">
          {missing} {tr("day(s) have no meal record. They are unknown, not days without eating.")}
        </p>
      )}
    </div>
  );
}

export function PlanCard({ plan }: { plan: NutritionPlan | null }) {
  if (!plan) {
    return (
      <p className="rounded-md border border-dashed border-line bg-canvas px-3 py-4 text-center text-sm text-ink-3">
        <Tx k="No nutrition plan has been approved by your care team yet." />
      </p>
    );
  }
  const limits = Object.entries(plan.prescribed_targets);
  return (
    <div className="space-y-2 text-sm">
      <p className="text-ink-3">
        {tr("Version")} {plan.version} · {tr("approved by")}{" "}
        <bdi>{tr(plan.approved_by_name ?? "")}</bdi> · <bdi>{dateOnly(plan.approved_at)}</bdi>
      </p>
      {plan.guidance && (
        <p className="text-base leading-7 text-ink" dir="auto">
          {tr(plan.guidance ?? "")}
        </p>
      )}
      {limits.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {limits.map(([key, limit]) => {
            const [name, unit] = NUTRIENT[key.replace(/_max$/, "") as NutrientKey] ?? [key, ""];
            return (
              <li key={key} className="rounded border border-line bg-chrome px-2 py-1">
                {tr(name)}: {tr("up to")} {withUnit(limit, unit)} {tr("per meal")}
              </li>
            );
          })}
        </ul>
      )}
      {plan.allergies.length > 0 && (
        <p>
          <span className="font-medium">{tr("Allergies")}:</span>{" "}
          {plan.allergies.map(tr).join("، ")}
        </p>
      )}
    </div>
  );
}

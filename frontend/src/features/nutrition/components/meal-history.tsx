"use client";

import { ErrorNote, Load, Section, Status } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AddMeal } from "@/features/nutrition/components/add-meal";
import { NutrientTray, unitName } from "@/features/nutrition/components/common";
import { type Meal } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { dateTime, label, today } from "@/lib/format";
import { useAction, useGet } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { History, Trash2 } from "lucide-react";
import { useState } from "react";
export function MealHistory({ patient, canLog }: { patient: string; canLog: boolean }) {
  const [from, setFrom] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 29);
    return date.toLocaleDateString("en-CA");
  });
  const [to, setTo] = useState(today);
  const [filter, setFilter] = useState("all");
  const [editing, setEditing] = useState<Meal | null>(null);
  const validPeriod = Boolean(from && to && from <= to);
  const meals = useGet<Meal[]>(
    validPeriod ? `/nutrition/meals/?patient=${patient}&from=${from}&to=${to}` : null,
  );
  const remove = useAction();
  if (editing)
    return (
      <AddMeal
        key={editing.id}
        patient={patient}
        diary="/patient/nutrition/history/"
        initialMeal={editing}
        onDone={() => {
          setEditing(null);
          meals.reload();
        }}
      />
    );
  return (
    <Section
      icon={History}
      title="Meal diary"
      description="Review meals, correct portions, and see which entries need checking."
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <label>
          {tr("From")}
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label>
          {tr("To")}
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <label>
          {tr("Show meals")}
          <select
            className="control w-full px-3"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">{tr("All meals")}</option>
            <option value="needs_review">{tr("Needs review")}</option>
            <option value="confirmed">{tr("Confirmed")}</option>
          </select>
        </label>
      </div>
      {!validPeriod && <ErrorNote message="Choose a valid date range." />}
      <ErrorNote message={remove.error} />
      {validPeriod && (
        <Load from={meals} empty="No meals recorded in this period.">
          {(rows) => (
            <ul className="space-y-3">
              {rows
                .filter((meal) => filter === "all" || meal.confirmation_status === filter)
                .map((meal) => (
                  <li key={meal.id} className="rounded-lg border border-line p-3">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-semibold">{label(meal.meal_type)}</span>
                      <time className="text-ink-3">{dateTime(meal.consumed_at)}</time>
                      <Status value={meal.confirmation_status} />
                      <span className="text-ink-3">
                        {tr("Recorded by")} {tr(meal.created_by_name)}
                      </span>
                      {canLog && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="ms-auto"
                          onClick={() => setEditing(meal)}
                        >
                          <Tx k="Correct meal" />
                        </Button>
                      )}
                      {canLog && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="ms-auto"
                          disabled={remove.pending}
                          onClick={async () =>
                            (await remove.run(() => api.del(`/nutrition/meals/${meal.id}/`))) &&
                            meals.reload()
                          }
                        >
                          <Trash2 className="size-4" aria-hidden />
                          <Tx k="Remove" />
                        </Button>
                      )}
                    </div>
                    <p className="my-2 text-sm" dir="auto">
                      {meal.components
                        .map(
                          (c) =>
                            `${tr(c.food_name || c.name)} (${Number(c.quantity)} ${unitName(c.unit)}${c.food_item ? "" : ` · ${tr("not in the food list")}`})`,
                        )
                        .join(" · ")}
                    </p>
                    {meal.confirmation_status === "needs_review" && (
                      <p className="mb-2 text-sm text-warn">
                        {tr("Check the selected foods and portions to complete this entry.")}
                      </p>
                    )}
                    <details>
                      <summary className="cursor-pointer text-sm font-medium text-brand">
                        {tr("Show nutrition estimates")}
                      </summary>
                      <div className="mt-2">
                        <NutrientTray values={meal.estimate} dense />
                      </div>
                    </details>
                  </li>
                ))}
              {!rows.some((meal) => filter === "all" || meal.confirmation_status === filter) && (
                <li>{tr("No meals match this filter.")}</li>
              )}
            </ul>
          )}
        </Load>
      )}
    </Section>
  );
}

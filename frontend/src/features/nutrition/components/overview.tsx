"use client";

import { Section, Stats } from "@/components/feedback";
import {
  DiaryFacts,
  Disclaimer,
  NutrientTray,
  PlanCard,
} from "@/features/nutrition/components/common";
import { type NutritionOverview } from "@/features/nutrition/types";
import { tr, Tx } from "@/lib/i18n";
import { ClipboardList, History, Plus, UtensilsCrossed } from "lucide-react";
import Link from "next/link";
export function Overview({
  data,
  add,
  showPlan = true,
}: {
  data: NutritionOverview;
  add?: string;
  showPlan?: boolean;
}) {
  return (
    <>
      <Stats
        items={[
          { label: "Meals today", value: data.today.meals_recorded, icon: UtensilsCrossed },
          {
            label: "Days recorded",
            value: `${data.last_7_days.days_recorded} / 7`,
            hint: "In the last 7 days",
          },
          {
            label: "Nutrition plan",
            value: data.active_plan ? tr("Approved") : tr("None yet"),
            tone: data.active_plan ? "ok" : "warn",
            hint: data.active_plan
              ? "Set by your care team"
              : "Ideas stay general until one is approved",
          },
        ]}
      />
      <Disclaimer />
      <Section
        icon={UtensilsCrossed}
        title="Today"
        description="Totals of the meals recorded today."
        action={
          add && (
            <Link
              href={add}
              className="inline-flex min-h-9 items-center gap-2 rounded-md bg-brand px-3 text-sm font-medium text-white hover:bg-brand-strong"
            >
              <Plus className="size-4" aria-hidden />
              <Tx k="Add a meal" />
            </Link>
          )
        }
      >
        {data.today.meals_recorded ? (
          <NutrientTray values={data.today.daily_average_on_complete_days} />
        ) : (
          <p className="text-sm text-ink-3">
            <Tx k="No meal recorded today." />
          </p>
        )}
      </Section>
      <Section icon={History} title="Last 7 days">
        <DiaryFacts summary={data.last_7_days} />
      </Section>
      {showPlan && (
        <Section
          icon={ClipboardList}
          title="Nutrition plan"
          description="Written and approved by a doctor or dietitian. The app never changes it."
        >
          <PlanCard plan={data.active_plan} />
        </Section>
      )}
    </>
  );
}

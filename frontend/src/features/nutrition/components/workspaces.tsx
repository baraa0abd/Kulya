"use client";

import { Load } from "@/components/feedback";
import { type NavItem, Shell } from "@/components/layout/shell";
import { Label } from "@/components/ui/label";
import { AddMeal } from "@/features/nutrition/components/add-meal";
import { Observations, PlanPanel } from "@/features/nutrition/components/care-plan";
import { LabPanel } from "@/features/nutrition/components/labs";
import { MealHistory } from "@/features/nutrition/components/meal-history";
import { Overview } from "@/features/nutrition/components/overview";
import { ReportsPanel } from "@/features/nutrition/components/reports";
import { Suggestions } from "@/features/nutrition/components/suggestions";
import { type NutritionOverview, type NutritionRow } from "@/features/nutrition/types";
import { HOME, useRole } from "@/lib/auth";
import { useGet } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import {
  ClipboardList,
  FileText,
  FlaskConical,
  History,
  LayoutDashboard,
  Plus,
  Salad,
  UtensilsCrossed,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
export type PatientView = "overview" | "add" | "history" | "suggestions" | "labs" | "reports";

const PATIENT_NAV: NavItem[] = [
  { href: "/patient/nutrition/", label: "Nutrition overview", icon: LayoutDashboard },
  { href: "/patient/nutrition/add/", label: "Add a meal", icon: Plus },
  { href: "/patient/nutrition/history/", label: "Meal diary", icon: History },
  { href: "/patient/nutrition/suggestions/", label: "Meal ideas", icon: Salad },
  { href: "/patient/nutrition/labs/", label: "Food and lab results", icon: FlaskConical },
  { href: "/patient/nutrition/reports/", label: "Nutrition reports", icon: FileText },
];

/** The patient's (or a consented caregiver's) nutrition area. One component, six routes. */
export function PatientNutrition({ view }: { view: PatientView }) {
  useLocale();
  const user = useRole("patient", "family");
  const isFamily = user?.role === "family";
  const shared = useGet<NutritionRow[]>(isFamily ? "/nutrition/overview/" : null);
  const [picked, setPicked] = useState<string | null>(null);
  const target = isFamily ? (picked ?? shared.data?.[0]?.patient ?? null) : "";
  const overview = useGet<NutritionOverview>(
    user && target !== null ? `/nutrition/overview/${target ? `?patient=${target}` : ""}` : null,
  );
  if (!user) return null;
  const nothingShared = isFamily && !shared.loading && !shared.data?.length;
  return (
    <Shell title="Nutrition" back="/patient/" nav={PATIENT_NAV}>
      {isFamily && (shared.data?.length ?? 0) > 1 && (
        <div className="flex items-center gap-2">
          <Label htmlFor="shared-patient">
            <Tx k="Patient" />
          </Label>
          <select
            id="shared-patient"
            className="control px-3"
            value={target ?? ""}
            onChange={(e) => setPicked(e.target.value)}
          >
            {shared.data?.map((row) => (
              <option key={row.patient} value={row.patient}>
                {tr(row.patient_name ?? "")}
              </option>
            ))}
          </select>
        </div>
      )}
      {nothingShared ? (
        <p className="rounded-md border border-dashed border-line bg-white px-3 py-6 text-center text-ink-3">
          <Tx k="No patient has shared their nutrition information with you." />
        </p>
      ) : (
        <Load from={overview}>
          {(data) => {
            if (view === "overview")
              return (
                <Overview data={data} add={data.can_log ? "/patient/nutrition/add/" : undefined} />
              );
            if (view === "history")
              return <MealHistory patient={data.patient} canLog={data.can_log} />;
            if (view === "suggestions")
              return <Suggestions patient={data.patient} canDecide={false} canRequest />;
            if (view === "labs") return <LabPanel patient={data.patient} canDecide={false} />;
            if (view === "reports")
              return <ReportsPanel patient={data.patient} canDecide={false} />;
            return data.can_log ? (
              <AddMeal
                patient={data.patient}
                diary="/patient/nutrition/history/"
                photoAvailable={data.photo_recognition_available}
              />
            ) : (
              <p className="rounded-md border border-dashed border-line bg-white px-3 py-6 text-center text-ink-3">
                <Tx k="The patient has not allowed you to record meals for them." />
              </p>
            );
          }}
        </Load>
      )}
    </Shell>
  );
}

export type ClinicianView = "overview" | "meals" | "lab-review" | "reports";

/** Care-team nutrition review of one patient. Doctors and dietitians decide; nurses read and observe. */
export function ClinicianNutrition({ view }: { view: ClinicianView }) {
  useLocale();
  const user = useRole("doctor", "dietitian", "nurse");
  const { id } = useParams<{ id: string }>();
  const overview = useGet<NutritionOverview>(user ? `/nutrition/overview/?patient=${id}` : null);
  if (!user) return null;
  const canDecide = user.role !== "nurse";
  const base = `/doctor/patients/${id}/nutrition/`;
  const nav: NavItem[] = [
    { href: `${base}meals/`, label: "Meal records", icon: UtensilsCrossed },
    { href: base, label: "Nutrition plan", icon: ClipboardList },
    { href: `${base}lab-review/`, label: "Food and lab results", icon: FlaskConical },
    { href: `${base}reports/`, label: "Nutrition reports", icon: FileText },
  ];
  const back = user.role === "doctor" ? `/doctor/patients/${id}/` : HOME[user.role];
  return (
    <Shell
      title={overview.data ? `${tr("Nutrition")} · ${tr(overview.data.patient_name)}` : "Nutrition"}
      back={back}
      nav={nav}
    >
      {view === "meals" && <MealHistory patient={id} canLog={false} />}
      {view === "lab-review" && <LabPanel patient={id} canDecide={canDecide} />}
      {view === "reports" && <ReportsPanel patient={id} canDecide={canDecide} />}
      {view === "overview" && (
        <>
          <Load from={overview}>{(data) => <Overview data={data} showPlan={false} />}</Load>
          <div className="flex flex-wrap gap-2">
            <a className="rounded-md border border-line bg-white px-3 py-2 text-brand" href="#plan">
              {tr("Nutrition plan")}
            </a>
            <a
              className="rounded-md border border-line bg-white px-3 py-2 text-brand"
              href="#observations"
            >
              {tr("Nursing observations about eating")}
            </a>
          </div>
          <PlanPanel patient={id} canDecide={canDecide} />
          <Suggestions
            patient={id}
            canDecide={canDecide}
            canDecideLabBased={user.role === "doctor"}
            canRequest={canDecide}
          />
          <Observations patient={id} canWrite={user.role === "nurse"} />
        </>
      )}
    </Shell>
  );
}

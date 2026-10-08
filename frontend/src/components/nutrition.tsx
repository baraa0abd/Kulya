"use client";

import {
  Camera,
  ClipboardList,
  FileText,
  FlaskConical,
  History,
  Info,
  LayoutDashboard,
  Mic,
  Plus,
  Printer,
  Salad,
  Sparkles,
  Stethoscope,
  Trash2,
  UtensilsCrossed,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { z } from "zod";

import { AiLabel, ErrorNote, Load, type NavItem, optionalNumber, requiredText, Section, Shell, Stats, Status, ZForm } from "@/components/app";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  type DiarySummary,
  type Food,
  type FoodLabReview,
  type LabFact,
  type LabTrendsData,
  type Meal,
  NUTRIENT_KEYS,
  type NutrientKey,
  type Nutrients,
  type NutritionObservation,
  type NutritionOverview,
  type NutritionPlan,
  type NutritionReport,
  type NutritionRow,
  type Recognition,
  type Recommendation,
} from "@/lib/api";
import { HOME, useRole } from "@/lib/auth";
import { dateOnly, dateTime, label, withUnit } from "@/lib/format";
import { useAction, useGet } from "@/lib/hooks";
import { getLocale, tr, Tx, useLocale } from "@/lib/i18n";

const NUTRIENT: Record<NutrientKey, [name: string, unit: string]> = {
  energy_kcal: ["Energy", "kcal"],
  protein_g: ["Protein", "g"],
  sodium_mg: ["Sodium", "mg"],
  potassium_mg: ["Potassium", "mg"],
  phosphorus_mg: ["Phosphorus", "mg"],
  calcium_mg: ["Calcium", "mg"],
  fluid_ml: ["Fluid", "mL"],
};
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
const UNIT_NAME: Record<string, string> = { g: "grams", ml: "millilitres" };
const unitName = (unit: string) => tr(UNIT_NAME[unit] ?? unit);
const localName = (names: Record<string, string>, fallback: string) => names[getLocale()] ?? fallback;

/** Shown wherever nutrient numbers or meal ideas appear. */
function Disclaimer() {
  return (
    <p className="flex items-start gap-2 rounded-md border border-line bg-chrome px-3 py-2 text-sm text-ink-2">
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
      <Tx k="Estimates only, from a demonstration food list that has not been verified. This is not medical advice: ask your care team before changing what you eat." />
    </p>
  );
}

/** Nutrient figures with units. A value that is not available says so; it is never shown as 0. */
export function NutrientTray({ values, dense = false }: { values: Nutrients | null; dense?: boolean }) {
  useLocale();
  return (
    <dl className={`grid grid-cols-2 gap-2 sm:grid-cols-4 ${dense ? "" : "xl:grid-cols-7"}`}>
      {NUTRIENT_KEYS.map((key) => {
        const value = values?.[key] ?? null;
        const [name, unit] = NUTRIENT[key];
        return (
          <div key={key} className={`rounded-md border p-2.5 ${value === null ? "border-warn/25 bg-warn-soft" : "border-line bg-chrome"}`}>
            <dt className="micro text-ink-2">{tr(name)}</dt>
            <dd className={`mt-0.5 font-semibold ${value === null ? "text-sm text-warn" : "text-lg text-ink"}`}>
              {value === null ? tr("Not available") : withUnit(value, unit)}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function DiaryFacts({ summary }: { summary: DiarySummary }) {
  const missing = summary.days_in_period - summary.days_recorded;
  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-2">
        {tr("Daily average on days with complete records.")} {tr("Meals recorded on")} {summary.days_recorded} {tr("of")}{" "}
        {summary.days_in_period} {tr("days")}.
      </p>
      <NutrientTray values={summary.daily_average_on_complete_days} />
      {missing > 0 && (
        <p className="rounded-md border border-warn/25 bg-warn-soft px-3 py-2 text-sm text-warn">
          {missing} {tr("day(s) have no meal record. They are unknown, not days without eating.")}
        </p>
      )}
    </div>
  );
}

function PlanCard({ plan }: { plan: NutritionPlan | null }) {
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
        {tr("Version")} {plan.version} · {tr("approved by")} <bdi>{plan.approved_by_name}</bdi> · <bdi>{dateOnly(plan.approved_at)}</bdi>
      </p>
      {plan.guidance && (
        <p className="text-base leading-7 text-ink" dir="auto">
          {plan.guidance}
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
          <span className="font-medium">{tr("Allergies")}:</span> {plan.allergies.join(", ")}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Diary
// ---------------------------------------------------------------------------------------------

function Overview({ data, add, showPlan = true }: { data: NutritionOverview; add?: string; showPlan?: boolean }) {
  return (
    <>
      <Stats
        items={[
          { label: "Meals today", value: data.today.meals_recorded, icon: UtensilsCrossed },
          { label: "Days recorded", value: `${data.last_7_days.days_recorded} / 7`, hint: "In the last 7 days" },
          {
            label: "Nutrition plan",
            value: data.active_plan ? tr("Approved") : tr("None yet"),
            tone: data.active_plan ? "ok" : "warn",
            hint: data.active_plan ? "Set by your care team" : "Ideas stay general until one is approved",
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
            <Link href={add} className="inline-flex min-h-9 items-center gap-2 rounded-md bg-brand px-3 text-sm font-medium text-white hover:bg-brand-strong">
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
        <Section icon={ClipboardList} title="Nutrition plan" description="Written and approved by a doctor or dietitian. The app never changes it.">
          <PlanCard plan={data.active_plan} />
        </Section>
      )}
    </>
  );
}

function MealHistory({ patient, canLog }: { patient: string; canLog: boolean }) {
  const meals = useGet<Meal[]>(`/nutrition/meals/?patient=${patient}`);
  const remove = useAction();
  return (
    <Section icon={History} title="Meal diary" description="The last 30 days, newest first.">
      <ErrorNote message={remove.error} />
      <Load from={meals} empty="No meals recorded in this period.">
        {(rows) => (
          <ul className="space-y-3">
            {rows.map((meal) => (
              <li key={meal.id} className="rounded-lg border border-line p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold">{label(meal.meal_type)}</span>
                  <time className="text-ink-3">{dateTime(meal.consumed_at)}</time>
                  <Status value={meal.confirmation_status} />
                  <span className="text-ink-3">
                    {tr("Recorded by")} {meal.created_by_name}
                  </span>
                  {canLog && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="ms-auto"
                      disabled={remove.pending}
                      onClick={async () => (await remove.run(() => api.del(`/nutrition/meals/${meal.id}/`))) && meals.reload()}
                    >
                      <Trash2 className="size-4" aria-hidden />
                      <Tx k="Remove" />
                    </Button>
                  )}
                </div>
                <p className="my-2 text-sm" dir="auto">
                  {meal.components
                    .map((c) => `${c.name} (${Number(c.quantity)} ${unitName(c.unit)}${c.food_item ? "" : ` · ${tr("not in the food list")}`})`)
                    .join(" · ")}
                </p>
                <NutrientTray values={meal.estimate} />
              </li>
            ))}
          </ul>
        )}
      </Load>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------
// Adding a meal: describe (type, speak or photograph) -> check every line -> save
// ---------------------------------------------------------------------------------------------

interface Row {
  key: number;
  name: string;
  food: string;
  quantity: string;
  unit: string;
  checked: boolean;
  unsure: boolean;
}
type Speech = {
  lang: string;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  start(): void;
};
const speechCtor = () => {
  const w = window as unknown as Record<string, (new () => Speech) | undefined>;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
};
const noop = () => () => {};

/** Downscale to 1024 px JPEG in the browser: small upload, and re-encoding drops location metadata. */
async function shrink(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1024 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.8).split(",")[1];
}

const localNow = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

function AddMeal({ patient, diary }: { patient: string; diary: string }) {
  const foods = useGet<Food[]>("/nutrition/foods/");
  const canSpeak = useSyncExternalStore(noop, () => Boolean(speechCtor()), () => false);
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [method, setMethod] = useState<"text" | "voice" | "photo">("text");
  const [listening, setListening] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [mealType, setMealType] = useState("lunch");
  const [when, setWhen] = useState(localNow);
  const [saved, setSaved] = useState<Meal | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const find = useAction();
  const save = useAction();
  const byId = new Map((foods.data ?? []).map((f) => [f.id, f]));
  const blank = (): Row => ({ key: Date.now() + Math.random(), name: "", food: "", quantity: "1", unit: "serving", checked: false, unsure: false });
  const edit = (key: number, change: Partial<Row>) => setRows((all) => all.map((r) => (r.key === key ? { ...r, ...change } : r)));

  const speak = () => {
    const Ctor = speechCtor();
    if (!Ctor) return;
    const recognition = new Ctor();
    recognition.lang = getLocale() === "ar" ? "ar-IQ" : "en-US";
    recognition.onresult = (event) => {
      setDescription((text) => `${text} ${event.results[0][0].transcript}`.trim());
      setMethod("voice");
    };
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  };

  const recognize = () =>
    find.run(async () => {
      const result = await api.post<Recognition>("/nutrition/ai/recognize/", {
        patient,
        description,
        ...(photo ? { image_base64: photo } : {}),
      });
      setNotes(result.ai_unavailable ? [tr("The assistant is unavailable right now. Add the foods yourself below.")] : result.uncertainties.map(tr));
      setRows(
        result.items.length
          ? result.items.map((item, i) => ({
              key: Date.now() + i,
              name: item.name,
              food: item.food_item ?? "",
              quantity: String(item.quantity),
              unit: item.unit,
              checked: false,
              unsure: item.confidence < 0.7,
            }))
          : [blank()],
      );
    });

  const submit = async () => {
    const parts = rows.filter((r) => r.name.trim() || r.food);
    if (!parts.length || parts.some((r) => !(Number(r.quantity) > 0))) {
      setProblem(tr("Add at least one food, each with an amount above zero."));
      return;
    }
    setProblem(null);
    await save.run(async () => {
      const meal = await api.post<Meal>("/nutrition/meals/", {
        patient,
        meal_type: mealType,
        consumed_at: new Date(when).toISOString(),
        entry_method: method,
        description,
        media_used: method === "text" ? "" : method,
        components: parts.map((r) => ({
          food_item: r.food || null,
          name: r.name.trim() || byId.get(r.food)?.canonical_name,
          quantity: Number(r.quantity),
          unit: r.unit,
          portion_verified: r.checked,
        })),
      });
      setSaved(meal);
      setRows([]);
      setDescription("");
      setPhoto(null);
      setNotes([]);
    });
  };

  if (saved) {
    return (
      <Section icon={UtensilsCrossed} title="Meal saved" action={<Status value={saved.confirmation_status} />}>
        <div className="space-y-3">
          {saved.confirmation_status === "needs_review" && (
            <p className="text-sm text-warn">
              <Tx k="Some foods or portions are not confirmed, so some values are not available." />
            </p>
          )}
          <NutrientTray values={saved.estimate} />
          <Disclaimer />
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setSaved(null)}>
              <Tx k="Add another meal" />
            </Button>
            <Link href={diary} className="inline-flex min-h-9 items-center rounded-md border border-line bg-white px-3 text-sm font-medium hover:bg-chrome">
              <Tx k="Open the diary" />
            </Link>
          </div>
        </div>
      </Section>
    );
  }

  return (
    <>
      <Section icon={Sparkles} tone="ai" title="1. Describe the meal" description="Type it, say it, or take a photo. The assistant only suggests: you check every line before anything is saved.">
        <div className="space-y-3">
          <Label htmlFor="meal-description">
            <Tx k="What did you eat?" />
          </Label>
          <Textarea
            id="meal-description"
            rows={3}
            dir="auto"
            value={description}
            placeholder={tr("For example: 2 boiled eggs, 1 piece bread, 1 glass tea")}
            onChange={(event) => setDescription(event.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            {canSpeak && (
              <Button type="button" variant="outline" onClick={speak} disabled={listening} aria-pressed={listening}>
                <Mic className="size-4" aria-hidden />
                {listening ? tr("Listening…") : tr("Speak")}
              </Button>
            )}
            <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium hover:bg-chrome">
              <Camera className="size-4" aria-hidden />
              {photo ? tr("Photo attached") : tr("Take or choose a photo")}
              <input
                type="file"
                accept="image/*"
                capture="environment"
                className="sr-only"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  setPhoto(await shrink(file));
                  setMethod("photo");
                }}
              />
            </label>
            <Button type="button" onClick={recognize} disabled={find.pending || (!description.trim() && !photo)}>
              {find.pending ? tr("Looking…") : tr("Find foods")}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setRows((all) => [...all, blank()])}>
              <Plus className="size-4" aria-hidden />
              <Tx k="Add a food myself" />
            </Button>
          </div>
          <p className="text-xs text-ink-3">
            <Tx k="The photo is used once to suggest foods and is not stored. Speaking uses your browser's own speech service." />
          </p>
          <ErrorNote message={find.error} />
          {notes.map((note) => (
            <p key={note} className="rounded-md border border-warn/25 bg-warn-soft px-3 py-2 text-sm text-warn" dir="auto">
              {note}
            </p>
          ))}
        </div>
      </Section>

      {rows.length > 0 && (
        <Section icon={ClipboardList} title="2. Check and save" description="Correct the food and amount on each line, then tick it when it is right.">
          <div className="space-y-3">
            {rows.map((row, index) => {
              const food = byId.get(row.food);
              const units = [...new Set([...(food ? Object.keys(food.portion_grams) : ["serving", "piece", "cup"]), "g", row.unit])];
              const perUnit = row.unit === "g" ? 1 : food?.portion_grams[row.unit];
              const n = index + 1;
              return (
                <fieldset key={row.key} className={`grid gap-2 rounded-lg border p-3 sm:grid-cols-12 ${row.checked ? "border-ok/30" : "border-warn/30"}`}>
                  <legend className="sr-only">
                    {tr("Food")} {n}
                  </legend>
                  <div className="space-y-1 sm:col-span-4">
                    <Label htmlFor={`name-${row.key}`}>
                      <Tx k="What it was" />
                    </Label>
                    <Input id={`name-${row.key}`} dir="auto" value={row.name} onChange={(e) => edit(row.key, { name: e.target.value })} />
                  </div>
                  <div className="space-y-1 sm:col-span-4">
                    <Label htmlFor={`food-${row.key}`}>
                      <Tx k="Food in the list" />
                    </Label>
                    <select
                      id={`food-${row.key}`}
                      className="control w-full px-3"
                      value={row.food}
                      onChange={(e) => {
                        const next = byId.get(e.target.value);
                        edit(row.key, { food: e.target.value, unit: next ? Object.keys(next.portion_grams)[0] : row.unit, checked: false });
                      }}
                    >
                      <option value="">{tr("Not in the list (values unknown)")}</option>
                      {(foods.data ?? []).map((f) => (
                        <option key={f.id} value={f.id}>
                          {localName(f.localized_names, f.canonical_name)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1 sm:col-span-2">
                    <Label htmlFor={`qty-${row.key}`}>
                      <Tx k="Amount" />
                    </Label>
                    <Input
                      id={`qty-${row.key}`}
                      inputMode="decimal"
                      value={row.quantity}
                      onChange={(e) => edit(row.key, { quantity: e.target.value, checked: false })}
                    />
                  </div>
                  <div className="space-y-1 sm:col-span-2">
                    <Label htmlFor={`unit-${row.key}`}>
                      <Tx k="Unit" />
                    </Label>
                    <select id={`unit-${row.key}`} className="control w-full px-3" value={row.unit} onChange={(e) => edit(row.key, { unit: e.target.value, checked: false })}>
                      {units.map((unit) => (
                        <option key={unit} value={unit}>
                          {unitName(unit)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm sm:col-span-12">
                    <label className="flex min-h-9 items-center gap-2 font-medium">
                      <input type="checkbox" className="size-5" checked={row.checked} onChange={(e) => edit(row.key, { checked: e.target.checked })} />
                      <Tx k="This food and amount are right" />
                    </label>
                    {perUnit && Number(row.quantity) > 0 && (
                      <span className="text-ink-3">
                        {tr("about")} {withUnit(Math.round(perUnit * Number(row.quantity)), "g")}
                      </span>
                    )}
                    {row.unsure && !row.checked && <span className="text-warn">{tr("The assistant was not sure. Please check.")}</span>}
                    <Button type="button" size="sm" variant="ghost" className="ms-auto" onClick={() => setRows((all) => all.filter((r) => r.key !== row.key))}>
                      <Trash2 className="size-4" aria-hidden />
                      <Tx k="Remove" />
                    </Button>
                  </div>
                </fieldset>
              );
            })}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="meal-type">
                  <Tx k="Meal" />
                </Label>
                <select id="meal-type" className="control w-full px-3" value={mealType} onChange={(e) => setMealType(e.target.value)}>
                  {MEAL_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {label(type)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="meal-when">
                  <Tx k="When" />
                </Label>
                <Input id="meal-when" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={submit} disabled={save.pending}>
                {save.pending ? tr("Saving…") : tr("Save meal")}
              </Button>
              <ErrorNote message={problem ?? save.error} />
            </div>
          </div>
        </Section>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------------------------
// Meal ideas, laboratory view, reports (shared by the patient and the care team)
// ---------------------------------------------------------------------------------------------

function Suggestions({ patient, canDecide, canRequest }: { patient: string; canDecide: boolean; canRequest: boolean }) {
  const path = `/nutrition/ai/suggestions/?patient=${patient}`;
  const ideas = useGet<Recommendation[]>(path);
  const act = useAction();
  const decide = async (id: string, approve: boolean) =>
    (await act.run(() => api.post(`/nutrition/recommendations/${id}/review/`, { approve }))) && ideas.reload();
  return (
    <Section
      id="suggestions"
      icon={Salad}
      title="Meal ideas"
      description="Recipes are compared with the approved plan by fixed rules. A personalized idea is shown to the patient only after a doctor or dietitian approves it."
      action={
        canRequest && (
          <Button
            variant="outline"
            disabled={act.pending}
            onClick={async () => (await act.run(() => api.post("/nutrition/ai/suggestions/", { patient }))) && ideas.reload()}
          >
            <Tx k="Look for meal ideas" />
          </Button>
        )
      }
    >
      <div className="space-y-3">
        <Disclaimer />
        <ErrorNote message={act.error} />
        <Load from={ideas} empty="No meal ideas to show yet.">
          {(rows) => (
            <ul className="grid gap-3 lg:grid-cols-2">
              {rows.map((idea) => (
                <li key={idea.id} className="space-y-2 rounded-lg border border-line p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold" dir="auto">
                      {localName(idea.recipe.localized_names, idea.recipe.name)}
                    </h3>
                    <Status value={idea.category} />
                    {canDecide && <Status value={idea.review_status} />}
                  </div>
                  <p className="micro text-ink-3">
                    {idea.personalized ? tr("Compared with the approved plan") : tr("General idea, not personalized")}
                    {idea.reviewed_by_name && idea.review_status === "approved" ? ` · ${tr("approved by")} ${idea.reviewed_by_name}` : ""}
                  </p>
                  <p className="text-sm leading-6" dir="auto">
                    {tr(idea.reasoning_summary)}
                  </p>
                  <NutrientTray values={idea.nutrient_estimates} dense />
                  <details className="text-sm">
                    <summary className="cursor-pointer font-medium text-brand">{tr("How to prepare")}</summary>
                    <ol className="mt-1 list-decimal space-y-1 ps-5" dir="auto">
                      {idea.recipe.preparation_method.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </details>
                  <ul className="list-disc ps-5 text-xs text-ink-3">
                    {idea.limitations.map((note) => (
                      <li key={note}>{tr(note)}</li>
                    ))}
                  </ul>
                  {canDecide && idea.review_status === "pending" && (
                    <div className="flex gap-2">
                      <Button size="sm" disabled={act.pending} onClick={() => decide(idea.id, true)}>
                        <Tx k="Approve" />
                      </Button>
                      <Button size="sm" variant="outline" disabled={act.pending} onClick={() => decide(idea.id, false)}>
                        <Tx k="Reject" />
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Load>
      </div>
    </Section>
  );
}

function LabTable({ labs }: { labs: LabFact[] }) {
  if (!labs.length) {
    return (
      <p className="text-sm text-ink-3">
        <Tx k="No laboratory results to show for this period." />
      </p>
    );
  }
  return (
    <ul className="divide-y divide-line text-sm">
      {labs.map((lab) => (
        <li key={lab.id} className="flex flex-wrap gap-x-4 gap-y-1 py-1.5">
          <span className="font-medium">{lab.analyte}</span>
          <span className="font-semibold">{withUnit(lab.value, lab.unit)}</span>
          {lab.reference_low !== null && lab.reference_high !== null && (
            <span className="text-ink-3">
              {tr("laboratory range")} <span dir="ltr">{`${lab.reference_low}–${lab.reference_high} ${lab.unit}`}</span>
            </span>
          )}
          <time className="ms-auto text-ink-3">{dateOnly(lab.collected_at)}</time>
        </li>
      ))}
    </ul>
  );
}

const noteSchema = z.object({ notes: z.string().trim().max(2000) });

function ReviewCard({ review, canDecide, onChange }: { review: FoodLabReview; canDecide: boolean; onChange: () => void }) {
  const open = review.review_status === "pending" || review.review_status === "ai_unavailable";
  const send = (approve: boolean) => async (values: { notes: string }) => {
    await api.post(`/nutrition/lab-reviews/${review.id}/review/`, { approve, notes: values.notes });
    onChange();
  };
  return (
    <li className="space-y-2 rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">
          {dateOnly(review.date_from)} – {dateOnly(review.date_to)}
        </span>
        <Status value={review.review_status} />
        {review.reviewed_by_name && <span className="text-ink-3">{review.reviewed_by_name}</span>}
      </div>
      {review.review_status === "approved" ? (
        <p className="micro text-ok">{tr("Reviewed by a clinician")}</p>
      ) : (
        <AiLabel text="Unverified draft. It describes records side by side and does not show that food changed any result." />
      )}
      {review.ai_error.length > 0 && <p className="text-sm text-bad">{tr("The AI draft was unavailable or rejected by the safety checks. The recorded facts are still shown.")}</p>}
      <ul className="list-disc space-y-1 ps-5 text-sm leading-6" dir="auto">
        {review.possible_associations.map((item) => (
          <li key={item.text}>{item.text}</li>
        ))}
      </ul>
      {review.questions.length > 0 && canDecide && (
        <ul className="list-disc ps-5 text-sm text-ink-2" dir="auto">
          {review.questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
      )}
      <ul className="list-disc ps-5 text-xs text-ink-3">
        {review.limitations.map((note) => (
          <li key={note}>{tr(note)}</li>
        ))}
      </ul>
      {review.review_notes && (
        <p className="text-sm" dir="auto">
          <span className="font-medium">{tr("Clinician note")}:</span> {review.review_notes}
        </p>
      )}
      {canDecide && open && (
        <div className="grid gap-2 lg:grid-cols-2">
          <ZForm schema={noteSchema} submitLabel="Approve for the patient" fields={[{ name: "notes", label: "Clinician note", type: "textarea" }]} onSubmit={send(true)} />
          <ZForm schema={noteSchema} submitLabel="Reject draft" fields={[{ name: "notes", label: "Reason", type: "textarea" }]} onSubmit={send(false)} />
        </div>
      )}
    </li>
  );
}

function LabPanel({ patient, canDecide }: { patient: string; canDecide: boolean }) {
  const trends = useGet<LabTrendsData>(`/nutrition/patients/${patient}/lab-trends/`);
  const analyze = useAction();
  return (
    <>
      <Section icon={FlaskConical} title="Food diary and laboratory results" description="The last 30 days, shown side by side. Many things other than food affect laboratory results.">
        <Load from={trends}>
          {(data) => (
            <div className="space-y-4">
              <DiaryFacts summary={data.diary} />
              <LabTable labs={data.laboratory_results} />
            </div>
          )}
        </Load>
      </Section>
      <Section
        icon={Sparkles}
        tone="ai"
        title="Food and laboratory review"
        description="A descriptive draft for the clinician. It never states a cause."
        action={
          canDecide && (
            <Button
              variant="outline"
              disabled={analyze.pending}
              onClick={async () => (await analyze.run(() => api.post("/nutrition/ai/analyze/", { patient }))) && trends.reload()}
            >
              <Tx k="Draft a review" />
            </Button>
          )
        }
      >
        <ErrorNote message={analyze.error} />
        <Load from={trends}>
          {(data) =>
            data.reviews.length ? (
              <ul className="space-y-3">
                {data.reviews.map((review) => (
                  <ReviewCard key={review.id} review={review} canDecide={canDecide} onChange={trends.reload} />
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">
                <Tx k="No review has been shared yet." />
              </p>
            )
          }
        </Load>
      </Section>
    </>
  );
}

const releaseSchema = z.object({ clinician_review: z.string().trim().max(4000) });

function ReportCard({ report, canDecide, onChange }: { report: NutritionReport; canDecide: boolean; onChange: () => void }) {
  const draft = report.ai_draft;
  const summary = report.meal_summary;
  return (
    <li className="space-y-3 rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">
          {report.patient_name} · {dateOnly(report.period_start)} – {dateOnly(report.period_end)}
        </h3>
        <Status value={report.release_status} />
        <span className="text-sm text-ink-3">
          {tr("Version")} {report.version}
        </span>
        <Button size="sm" variant="outline" className="no-print ms-auto" onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden />
          <Tx k="Print or save as PDF" />
        </Button>
      </div>
      <h4 className="micro text-ink-2">{tr("Recorded facts")}</h4>
      <p className="text-sm">
        {tr("Meals recorded on")} {summary.days_recorded} {tr("of")} {summary.days_in_period} {tr("days")} · {summary.meals_recorded} {tr("meals")}
      </p>
      <NutrientTray values={report.nutrient_summary.daily_average_on_complete_days} />
      <LabTable labs={report.laboratory_summary} />
      <p className="text-sm text-ink-2">
        {tr("Dialysis sessions in this period")}: {report.dialysis_summary.length}
      </p>
      <h4 className="micro text-ink-2">{tr("Narrative")}</h4>
      {draft ? (
        <div className="space-y-2 rounded-md border-s-4 border-s-ai bg-ai-soft/40 p-3">
          {report.release_status === "released" ? (
            <p className="micro text-ok">
              {tr("AI-drafted, reviewed and released by")} {report.reviewed_by_name}
            </p>
          ) : (
            <AiLabel text="Unverified draft. Not visible to the patient until a clinician releases this report." />
          )}
          <p className="leading-7" dir="auto">
            {draft.overview}
          </p>
          <ul className="list-disc ps-5 text-sm" dir="auto">
            {draft.observations.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <ul className="list-disc ps-5 text-xs text-ink-3">
            {draft.limitations.map((note) => (
              <li key={note}>{tr(note)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-ink-3">{tr("No AI narrative: it was unavailable or rejected by the safety checks.")}</p>
      )}
      {report.clinician_review && (
        <p className="text-sm" dir="auto">
          <span className="font-medium">{tr("Clinician note")}:</span> {report.clinician_review}
        </p>
      )}
      {canDecide && report.release_status !== "released" && (
        <div className="no-print">
          <ZForm
            schema={releaseSchema}
            submitLabel="Release to the patient"
            fields={[{ name: "clinician_review", label: "Clinician note", type: "textarea" }]}
            onSubmit={async (values) => {
              await api.post(`/nutrition/reports/${report.id}/release/`, values);
              onChange();
            }}
          />
        </div>
      )}
    </li>
  );
}

function ReportsPanel({ patient, canDecide }: { patient: string; canDecide: boolean }) {
  const base = `/nutrition/patients/${patient}/reports/`;
  const reports = useGet<NutritionReport[]>(base);
  const build = useAction();
  return (
    <Section
      icon={FileText}
      title="Nutrition reports"
      description="Facts are calculated from the records. The narrative is an AI draft that a doctor or dietitian reviews before release."
      action={
        canDecide && (
          <Button variant="outline" className="no-print" disabled={build.pending} onClick={async () => (await build.run(() => api.post(`${base}generate/`, {}))) && reports.reload()}>
            <Tx k="Draft a report for the last 30 days" />
          </Button>
        )
      }
    >
      <ErrorNote message={build.error} />
      <Load from={reports} empty={canDecide ? "No report has been drafted yet." : "No report has been released yet."}>
        {(rows) => (
          <ul className="space-y-4">
            {rows.map((report) => (
              <ReportCard key={report.id} report={report} canDecide={canDecide} onChange={reports.reload} />
            ))}
          </ul>
        )}
      </Load>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------
// Care team: plan approval and nursing observations
// ---------------------------------------------------------------------------------------------

const limit = optionalNumber(1, 100000);
const planSchema = z.object({
  potassium_mg_max: limit,
  sodium_mg_max: limit,
  phosphorus_mg_max: limit,
  fluid_ml_max: limit,
  allergies: z.string().trim().max(400),
  guidance: z.string().trim().max(2000),
});
const words = (text: string) => text.split(/[,،]/).map((w) => w.trim()).filter(Boolean);

function PlanPanel({ patient, canDecide }: { patient: string; canDecide: boolean }) {
  const path = `/nutrition/patients/${patient}/plans/`;
  const plans = useGet<NutritionPlan[]>(path);
  return (
    <Section id="plan" icon={ClipboardList} title="Nutrition plan" description="Only a doctor or dietitian approves a plan. Saving creates a new version; earlier versions are kept.">
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
      {canDecide && (
        <ZForm
          schema={planSchema}
          submitLabel="Approve new plan version"
          fields={[
            { name: "potassium_mg_max", label: "Potassium limit per meal (mg)", type: "number" },
            { name: "sodium_mg_max", label: "Sodium limit per meal (mg)", type: "number" },
            { name: "phosphorus_mg_max", label: "Phosphorus limit per meal (mg)", type: "number" },
            { name: "fluid_ml_max", label: "Fluid limit per meal (mL)", type: "number" },
            { name: "allergies", label: "Allergies (comma separated)", hint: "Recipes containing these are never suggested." },
            { name: "guidance", label: "Guidance for the patient", type: "textarea" },
          ]}
          onSubmit={async ({ allergies, guidance, ...limits }) => {
            const targets = Object.fromEntries(Object.entries(limits).filter(([, v]) => v !== undefined));
            await api.post(path, { prescribed_targets: targets, allergies: words(allergies), guidance });
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

function Observations({ patient, canWrite }: { patient: string; canWrite: boolean }) {
  const path = `/nutrition/patients/${patient}/observations/`;
  const notes = useGet<NutritionObservation[]>(path);
  return (
    <Section id="observations" icon={Stethoscope} title="Nursing observations about eating" description="A nurse records what the patient reports and can refer it to the doctor and dietitian.">
      <Load from={notes} empty="No observations recorded.">
        {(rows) => (
          <ul className="mb-4 divide-y divide-line text-sm">
            {rows.map((note) => (
              <li key={note.id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="font-medium">{label(note.kind)}</span>
                <span dir="auto">{note.text}</span>
                {note.referred && <span className="micro rounded border border-warn/25 bg-warn-soft px-1.5 text-warn">{tr("Referred")}</span>}
                <span className="ms-auto text-ink-3">
                  {note.author_name} · {dateOnly(note.created_at)}
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
            { name: "kind", label: "Observation", type: "select", options: ["eating_difficulty", "nausea", "loss_of_appetite", "other"].map((k): [string, string] => [k, label(k)]) },
            { name: "referred", label: "Refer to doctor and dietitian", type: "select", options: [["no", "No"], ["yes", "Yes"]] },
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

// ---------------------------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------------------------

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
  const overview = useGet<NutritionOverview>(user && target !== null ? `/nutrition/overview/${target ? `?patient=${target}` : ""}` : null);
  if (!user) return null;
  const nothingShared = isFamily && !shared.loading && !shared.data?.length;
  return (
    <Shell title="Nutrition" back="/patient/" nav={PATIENT_NAV}>
      {isFamily && (shared.data?.length ?? 0) > 1 && (
        <div className="flex items-center gap-2">
          <Label htmlFor="shared-patient">
            <Tx k="Patient" />
          </Label>
          <select id="shared-patient" className="control px-3" value={target ?? ""} onChange={(e) => setPicked(e.target.value)}>
            {shared.data?.map((row) => (
              <option key={row.patient} value={row.patient}>
                {row.patient_name}
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
            if (view === "overview") return <Overview data={data} add={data.can_log ? "/patient/nutrition/add/" : undefined} />;
            if (view === "history") return <MealHistory patient={data.patient} canLog={data.can_log} />;
            if (view === "suggestions") return <Suggestions patient={data.patient} canDecide={false} canRequest />;
            if (view === "labs") return <LabPanel patient={data.patient} canDecide={false} />;
            if (view === "reports") return <ReportsPanel patient={data.patient} canDecide={false} />;
            return data.can_log ? (
              <AddMeal patient={data.patient} diary="/patient/nutrition/history/" />
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

export type ClinicianView = "overview" | "lab-review" | "reports";

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
    { href: base, label: "Diary and plan", icon: UtensilsCrossed },
    { href: `${base}lab-review/`, label: "Food and lab results", icon: FlaskConical },
    { href: `${base}reports/`, label: "Nutrition reports", icon: FileText },
  ];
  const back = user.role === "doctor" ? `/doctor/patients/${id}/` : HOME[user.role];
  return (
    <Shell title={overview.data ? `${tr("Nutrition")} · ${overview.data.patient_name}` : "Nutrition"} back={back} nav={nav}>
      {view === "lab-review" && <LabPanel patient={id} canDecide={canDecide} />}
      {view === "reports" && <ReportsPanel patient={id} canDecide={canDecide} />}
      {view === "overview" && (
        <>
          <Load from={overview}>{(data) => <Overview data={data} showPlan={false} />}</Load>
          <PlanPanel patient={id} canDecide={canDecide} />
          <Suggestions patient={id} canDecide={canDecide} canRequest={canDecide} />
          <Observations patient={id} canWrite={user.role === "nurse"} />
          <MealHistory patient={id} canLog={false} />
        </>
      )}
    </Shell>
  );
}

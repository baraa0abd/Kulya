"use client";

import { ErrorNote, Load, Section, Status } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { shrink, speechCtor } from "@/features/nutrition/browser-input";
import {
  Disclaimer,
  localName,
  NutrientTray,
  unitName,
} from "@/features/nutrition/components/common";
import { type Food, type Meal, type Recognition } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { label, withUnit } from "@/lib/format";
import { useAction, useGet } from "@/lib/hooks";
import { getLocale, tr, Tx } from "@/lib/i18n";
import { mealAmount, validateMeal, type MealInput } from "@/features/nutrition/meal-input";
import { Camera, ClipboardList, Mic, Plus, Sparkles, Trash2, UtensilsCrossed } from "lucide-react";
import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];

interface Row extends MealInput {
  key: number;
  unsure: boolean;
}

const noop = () => () => {};

const localNow = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

const blankMealRow = (): Row => ({
  key: Date.now() + Math.random(),
  name: "",
  food: "",
  quantity: "1",
  unit: "serving",
  checked: false,
  unsure: false,
});

export function AddMeal({
  patient,
  diary,
  initialMeal,
  onDone,
  photoAvailable = false,
}: {
  patient: string;
  diary: string;
  initialMeal?: Meal;
  onDone?: () => void;
  photoAvailable?: boolean;
}) {
  const foods = useGet<Food[]>("/nutrition/foods/");
  const canSpeak = useSyncExternalStore(
    noop,
    () => Boolean(speechCtor()),
    () => false,
  );
  const [description, setDescription] = useState(initialMeal?.description ?? "");
  const [photo, setPhoto] = useState<string | null>(null);
  const [method, setMethod] = useState<"text" | "voice" | "photo">("text");
  const [listening, setListening] = useState(false);
  const [rows, setRows] = useState<Row[]>(() =>
    initialMeal
      ? initialMeal.components.map((part, i) => ({
          key: i,
          name: part.name,
          food: part.food_item ?? "",
          quantity: String(part.quantity),
          unit: part.unit,
          checked: part.portion_verified,
          unsure: false,
        }))
      : [
          {
            key: 0,
            name: "",
            food: "",
            quantity: "1",
            unit: "serving",
            checked: false,
            unsure: false,
          },
        ],
  );
  const [search, setSearch] = useState("");
  const [notes, setNotes] = useState<string[]>([]);
  const [mealType, setMealType] = useState(
    initialMeal?.meal_type ??
      (new Date().getHours() < 11 ? "breakfast" : new Date().getHours() < 17 ? "lunch" : "dinner"),
  );
  const [when, setWhen] = useState(() =>
    initialMeal
      ? new Date(
          new Date(initialMeal.consumed_at).getTime() - new Date().getTimezoneOffset() * 60000,
        )
          .toISOString()
          .slice(0, 16)
      : localNow(),
  );
  const [saved, setSaved] = useState<Meal | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const find = useAction();
  const save = useAction();
  const byId = new Map((foods.data ?? []).map((f) => [f.id, f]));
  const blank = blankMealRow;
  const edit = (key: number, change: Partial<Row>) =>
    setRows((all) => all.map((r) => (r.key === key ? { ...r, ...change } : r)));

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
    recognition.onerror = () => {
      setListening(false);
      setProblem("Speech input was unavailable. Type or choose foods instead.");
    };
    setListening(true);
    try {
      recognition.start();
    } catch {
      setListening(false);
      setProblem("Speech input was unavailable. Type or choose foods instead.");
    }
  };

  const recognize = () =>
    find.run(async () => {
      const result = await api.post<Recognition>("/nutrition/ai/recognize/", {
        patient,
        description,
        ...(photo ? { image_base64: photo } : {}),
      });
      setNotes(
        result.ai_unavailable
          ? ["The assistant is unavailable right now. Add the foods yourself below."]
          : result.uncertainties,
      );
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
    const validated = validateMeal(rows, when, byId, new Date());
    if (!validated.ok) {
      setProblem(validated.message);
      return;
    }
    setProblem(null);
    await save.run(async () => {
      const body = {
        patient,
        meal_type: mealType,
        consumed_at: validated.consumedAt,
        entry_method: method,
        description,
        media_used: method === "text" ? "" : method,
        components: validated.components,
      };
      const meal = initialMeal
        ? await api.patch<Meal>(`/nutrition/meals/${initialMeal.id}/`, body)
        : await api.post<Meal>("/nutrition/meals/", body);
      if (onDone) {
        onDone();
        return;
      }
      setSaved(meal);
      setRows([]);
      setDescription("");
      setPhoto(null);
      setNotes([]);
    });
  };

  if (saved) {
    return (
      <Section
        icon={UtensilsCrossed}
        title="Meal saved"
        action={<Status value={saved.confirmation_status} />}
      >
        <div className="space-y-3">
          {saved.confirmation_status === "needs_review" && (
            <p className="text-sm text-warn">
              <Tx k="Some foods or portions are not confirmed, so some values are not available." />
            </p>
          )}
          <NutrientTray values={saved.estimate} />
          <Disclaimer />
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => {
                setSaved(null);
                setRows([blank()]);
                setWhen(localNow());
              }}
            >
              <Tx k="Add another meal" />
            </Button>
            <Link
              href={diary}
              className="inline-flex min-h-9 items-center rounded-md border border-line bg-white px-3 text-sm font-medium hover:bg-chrome"
            >
              <Tx k="Open the diary" />
            </Link>
          </div>
        </div>
      </Section>
    );
  }

  return (
    <>
      {onDone && (
        <Button variant="outline" onClick={onDone}>
          <Tx k="Cancel correction" />
        </Button>
      )}
      <Section
        icon={UtensilsCrossed}
        title={initialMeal ? "Correct meal" : "Choose foods and portions"}
        description="Select familiar foods below. You can record a meal without using the assistant."
      >
        <Label htmlFor="food-search">
          <Tx k="Search the food list" />
        </Label>
        <Input
          id="food-search"
          value={search}
          placeholder={tr("Search by Arabic or English food name")}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Load from={foods} empty="No foods found.">
          {(catalog) => {
            const matches = catalog
              .filter((food) =>
                `${food.canonical_name} ${Object.values(food.localized_names).join(" ")}`
                  .toLowerCase()
                  .includes(search.trim().toLowerCase()),
              )
              .slice(0, 8);
            return (
              <div className="mt-3 flex flex-wrap gap-2">
                {matches.map((food) => (
                  <Button
                    key={food.id}
                    variant="outline"
                    onClick={() => {
                      const row = {
                        ...blank(),
                        food: food.id,
                        name: food.canonical_name,
                        unit: Object.keys(food.portion_grams)[0] ?? "g",
                      };
                      setRows((all) =>
                        all.length === 1 && !all[0].name && !all[0].food ? [row] : [...all, row],
                      );
                    }}
                  >
                    {localName(food.localized_names, food.canonical_name)}
                  </Button>
                ))}
                {!matches.length && <p>{tr("No foods found. Add an unlisted food below.")}</p>}
              </div>
            );
          }}
        </Load>
        <Button
          className="mt-3"
          variant="outline"
          onClick={() =>
            setRows((all) =>
              all.length === 1 && !all[0].name && !all[0].food ? all : [...all, blank()],
            )
          }
        >
          <Tx k="Add an unlisted food" />
        </Button>
      </Section>
      <details className="rounded-lg border border-line bg-white p-4">
        <summary className="cursor-pointer font-medium text-brand">
          {tr(
            photoAvailable
              ? "Optional: describe, speak, or attach a photo"
              : "Optional: describe or speak",
          )}
        </summary>
        {!photoAvailable && (
          <p className="mt-2 text-sm text-ink-3">
            {tr(
              "Offline mode: select foods or use text suggestions. Photo recognition is unavailable.",
            )}
          </p>
        )}
        <Section
          icon={Sparkles}
          tone="ai"
          title="1. Describe the meal"
          description="Type it, say it, or take a photo. The assistant only suggests: you check every line before anything is saved."
        >
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
                <Button
                  type="button"
                  variant="outline"
                  onClick={speak}
                  disabled={listening}
                  aria-pressed={listening}
                >
                  <Mic className="size-4" aria-hidden />
                  {listening ? tr("Listening…") : tr("Speak")}
                </Button>
              )}
              {photoAvailable && (
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
                      try {
                        setPhoto(await shrink(file));
                        setMethod("photo");
                        setProblem(null);
                      } catch {
                        setProblem(
                          "This photo could not be opened. Choose another image or enter foods directly.",
                        );
                      }
                    }}
                  />
                </label>
              )}
              <Button
                type="button"
                onClick={recognize}
                disabled={find.pending || (!description.trim() && !photo)}
              >
                {find.pending ? tr("Looking…") : tr("Find foods")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setRows((all) => [...all, blank()])}
              >
                <Plus className="size-4" aria-hidden />
                <Tx k="Add a food myself" />
              </Button>
            </div>
            <p className="text-xs text-ink-3">
              <Tx k="The photo is used once to suggest foods and is not stored. Speaking uses your browser's own speech service." />
            </p>
            <ErrorNote message={find.error} />
            {notes.map((note) => (
              <p
                key={note}
                className="rounded-md border border-warn/25 bg-warn-soft px-3 py-2 text-sm text-warn"
                dir="auto"
              >
                {tr(note)}
              </p>
            ))}
          </div>
        </Section>
      </details>

      {rows.length > 0 && (
        <Section
          icon={ClipboardList}
          title="2. Check and save"
          description="Correct the food and amount on each line, then tick it when it is right."
        >
          <div className="space-y-3">
            {rows.map((row, index) => {
              const food = byId.get(row.food);
              const units = [
                ...new Set([
                  ...(food ? Object.keys(food.portion_grams) : ["serving", "piece", "cup"]),
                  "g",
                  row.unit,
                ]),
              ];
              const perUnit = row.unit === "g" ? 1 : food?.portion_grams[row.unit];
              const n = index + 1;
              return (
                <fieldset
                  key={row.key}
                  className={`grid gap-2 rounded-lg border p-3 sm:grid-cols-12 ${row.checked ? "border-ok/30" : "border-warn/30"}`}
                >
                  <legend className="sr-only">
                    {tr("Food")} {n}
                  </legend>
                  <div className="space-y-1 sm:col-span-4">
                    <Label htmlFor={`name-${row.key}`}>
                      <Tx k="What it was" />
                    </Label>
                    <Input
                      id={`name-${row.key}`}
                      dir="auto"
                      value={food ? localName(food.localized_names, food.canonical_name) : row.name}
                      readOnly={Boolean(food)}
                      onChange={(e) => edit(row.key, { name: e.target.value, checked: false })}
                    />
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
                        edit(row.key, {
                          food: e.target.value,
                          name: next?.canonical_name ?? "",
                          unit: next ? Object.keys(next.portion_grams)[0] : row.unit,
                          checked: false,
                        });
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
                    <select
                      id={`unit-${row.key}`}
                      className="control w-full px-3"
                      value={row.unit}
                      onChange={(e) => edit(row.key, { unit: e.target.value, checked: false })}
                    >
                      {units.map((unit) => (
                        <option key={unit} value={unit}>
                          {unitName(unit)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm sm:col-span-12">
                    <label className="flex min-h-9 items-center gap-2 font-medium">
                      <input
                        type="checkbox"
                        className="size-5"
                        checked={row.checked}
                        onChange={(e) => edit(row.key, { checked: e.target.checked })}
                      />
                      <Tx k="This food and amount are right" />
                    </label>
                    {perUnit && mealAmount(row.quantity) > 0 && (
                      <span className="text-ink-3">
                        {tr("about")}{" "}
                        {withUnit(Math.round(perUnit * mealAmount(row.quantity)), "g")}
                      </span>
                    )}
                    {row.unsure && !row.checked && (
                      <span className="text-warn">
                        {tr("The assistant was not sure. Please check.")}
                      </span>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="ms-auto"
                      onClick={() => setRows((all) => all.filter((r) => r.key !== row.key))}
                    >
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
                <select
                  id="meal-type"
                  className="control w-full px-3"
                  value={mealType}
                  onChange={(e) => setMealType(e.target.value)}
                >
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
                <Input
                  id="meal-when"
                  type="datetime-local"
                  max={localNow()}
                  value={when}
                  onChange={(e) => setWhen(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => setRows((all) => [...all, blank()])}
              >
                <Tx k="Add a food myself" />
              </Button>
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

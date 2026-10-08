import type { Food, MealPart } from "./types";

/** Accept the decimal digits commonly typed by Arabic and English speakers. */
export function mealAmount(text: string): number {
  const normalized = text
    .trim()
    .replace(/[٠-٩]/g, (digit) => String(digit.charCodeAt(0) - 0x660))
    .replace(/[۰-۹]/g, (digit) => String(digit.charCodeAt(0) - 0x6f0))
    .replace(/[٫,]/g, ".");
  return /^\d+(?:\.\d+)?$/.test(normalized) ? Number(normalized) : NaN;
}

export interface MealInput {
  name: string;
  food: string;
  quantity: string;
  unit: string;
  checked: boolean;
}

type MealValidation =
  { ok: true; consumedAt: string; components: MealPart[] } | { ok: false; message: string };

/** Prepare a confirmed diary entry. The caller supplies the clock and catalogue. */
export function validateMeal(
  rows: MealInput[],
  when: string,
  foods: ReadonlyMap<string, Food>,
  now: Date,
): MealValidation {
  const parts = rows.filter((row) => row.name.trim() || row.food);
  const quantities = parts.map((row) => mealAmount(row.quantity));
  if (!parts.length || quantities.some((quantity) => !(quantity >= 0.01 && quantity <= 99999.99))) {
    return { ok: false, message: "Add at least one food, each with an amount above zero." };
  }
  const consumed = new Date(when);
  if (!when || !Number.isFinite(consumed.getTime()) || consumed.getTime() > now.getTime()) {
    return { ok: false, message: "Choose a meal time that is not in the future." };
  }
  if (parts.some((row) => !row.checked)) {
    return { ok: false, message: "Confirm each food and amount before saving." };
  }
  if (
    parts.some(
      (row) => row.food && row.unit !== "g" && !foods.get(row.food)?.portion_grams[row.unit],
    )
  ) {
    return { ok: false, message: "Choose a supported portion for each selected food." };
  }
  return {
    ok: true,
    consumedAt: consumed.toISOString(),
    components: parts.map((row, index) => ({
      food_item: row.food || null,
      name: foods.get(row.food)?.canonical_name ?? row.name.trim(),
      quantity: quantities[index],
      unit: row.unit,
      portion_verified: row.checked,
    })),
  };
}

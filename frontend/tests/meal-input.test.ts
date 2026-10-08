import { mealAmount, validateMeal, type MealInput } from "@/features/nutrition/meal-input";
import type { Food } from "@/features/nutrition/types";
import { expect, it } from "vitest";

it.each([
  ["1.5", 1.5],
  ["١٫٥", 1.5],
  ["۲,۵", 2.5],
  [" 2 ", 2],
])("accepts decimal portion %s", (input, result) => expect(mealAmount(input)).toBe(result));
it.each(["", "-1", "abc", "Infinity", "1e5", "١٢غ", "1.2.3"])(
  "rejects invalid portion %s",
  (input) => expect(mealAmount(input)).toBeNaN(),
);

const now = new Date("2026-10-08T12:00:00Z");
const when = "2026-10-08T10:00:00Z";
const food: Food = {
  id: "food",
  canonical_name: "cucumber",
  localized_names: {},
  portion_grams: { piece: 100 },
  allergens: [],
};
const foods = new Map([[food.id, food]]);
const row: MealInput = {
  name: "anything typed",
  food: food.id,
  quantity: "٢",
  unit: "piece",
  checked: true,
};

it("prepares Arabic portions with catalogue identity and does not mutate the input", () => {
  const result = validateMeal([row], when, foods, now);
  expect(result).toEqual({
    ok: true,
    consumedAt: when.replace("Z", ".000Z"),
    components: [
      { food_item: "food", name: "cucumber", quantity: 2, unit: "piece", portion_verified: true },
    ],
  });
  expect(row.name).toBe("anything typed");
});
it.each(["", "invalid", "2026-10-09T10:00:00Z"])("rejects invalid or future time %s", (time) => {
  expect(validateMeal([row], time, foods, now)).toMatchObject({
    ok: false,
    message: "Choose a meal time that is not in the future.",
  });
});
it("requires confirmed supported portions", () => {
  expect(validateMeal([{ ...row, checked: false }], when, foods, now)).toMatchObject({
    ok: false,
    message: "Confirm each food and amount before saving.",
  });
  expect(validateMeal([{ ...row, unit: "bucket" }], when, foods, now)).toMatchObject({
    ok: false,
    message: "Choose a supported portion for each selected food.",
  });
});
it("preserves an unlisted food without inventing a catalogue link", () => {
  const result = validateMeal([{ ...row, food: "", name: " homemade meal " }], when, foods, now);
  expect(result.ok && result.components[0]).toMatchObject({
    food_item: null,
    name: "homemade meal",
  });
});
it.each(["0", "100000", "abc"])("rejects unusable amount %s", (quantity) => {
  expect(validateMeal([{ ...row, quantity }], when, foods, now)).toMatchObject({ ok: false });
});

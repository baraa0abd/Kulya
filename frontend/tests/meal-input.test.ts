import { expect, it } from "vitest";
import { mealAmount } from "@/lib/meal-input";

it.each([["1.5", 1.5], ["١٫٥", 1.5], ["۲,۵", 2.5], [" 2 ", 2]])("accepts decimal portion %s", (input, result) => expect(mealAmount(input)).toBe(result));
it.each(["", "-1", "abc", "Infinity", "1e5", "١٢غ", "1.2.3"])("rejects invalid portion %s", input => expect(mealAmount(input)).toBeNaN());

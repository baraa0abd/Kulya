import { AR_CATALOG } from "@/lib/arabic-catalog";
import { hasArabicTranslation, setLocale, tr } from "@/lib/i18n";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import ts from "typescript";
import { afterEach, expect, it } from "vitest";

afterEach(() => setLocale("en", false));

it("provides Arabic for every declared interface label and message", () => {
  setLocale("ar", false);
  const missing = new Set<string>();
  const check = (text: string) => {
    if (!hasArabicTranslation(text) || /[a-z]/i.test(tr(text))) missing.add(text);
  };
  const displayKeys = new Set([
    "k",
    "title",
    "description",
    "empty",
    "submitLabel",
    "label",
    "hint",
    "placeholder",
    "aria-label",
  ]);
  function walk(dir: string) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = resolve(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "ui") walk(path);
        continue;
      }
      if (!/\.tsx?$/.test(path) || /[\\/]lib[\\/](i18n|arabic)/.test(path)) continue;
      const source = ts.createSourceFile(
        path,
        readFileSync(path, "utf8"),
        ts.ScriptTarget.Latest,
        true,
        path.endsWith("tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
      );
      function literals(node: ts.Node) {
        if (ts.isStringLiteral(node)) check(node.text);
        else ts.forEachChild(node, literals);
      }
      function visit(node: ts.Node) {
        if (ts.isJsxText(node) && /[a-z]/i.test(node.text)) check(node.text.trim());
        if (
          ts.isCallExpression(node) &&
          ["tr", "requiredText"].includes(node.expression.getText(source))
        ) {
          if (node.arguments[0] && ts.isStringLiteral(node.arguments[0]))
            check(node.arguments[0].text);
        }
        if (
          ts.isJsxAttribute(node) &&
          displayKeys.has(node.name.getText(source)) &&
          node.initializer
        )
          literals(node.initializer);
        if (
          ts.isPropertyAssignment(node) &&
          ["label", "hint"].includes(node.name.getText(source).replaceAll('"', ""))
        )
          literals(node.initializer);
        ts.forEachChild(node, visit);
      }
      visit(source);
    }
  }
  walk(resolve("src"));
  expect([...missing].sort()).toEqual([]);
});

it("translates every bundled food, recipe, and cooking instruction", () => {
  setLocale("ar", false);
  const catalog = JSON.parse(
    readFileSync(resolve("../backend/nutrition/data/catalog.json"), "utf8"),
  ) as {
    foods: { name: string; allergens: string[]; portions: Record<string, number> }[];
    recipes: { name: string; steps: string[] }[];
  };
  const sources = [
    ...Object.keys(AR_CATALOG),
    ...catalog.foods.flatMap((food) => [
      food.name,
      ...food.allergens,
      ...Object.keys(food.portions),
    ]),
    ...catalog.recipes.flatMap((recipe) => [recipe.name, ...recipe.steps]),
  ];
  for (const source of sources) {
    expect(tr(source)).toMatch(/[\u0600-\u06ff]/);
    expect(tr(source)).not.toMatch(/[a-z]/i);
  }
});

it.each([
  "No active account found with the given credentials",
  "Invalid input. value: Outside the plausible range 20-300 mmHg.",
  "Too small: expected string to have >=1 characters",
  "Invalid input. scheduled_start: Datetime has wrong format. Use one of these formats instead: iso-8601.",
  "3 documentation item(s) need attention for this session.",
  "Required documentation field is missing: pre_weight.",
  "Documented treatment duration 240 min (prescribed 240 min). 2 event(s) and 3 nursing action(s) recorded.",
  "Your dialysis session was recorded. 3 nursing step(s) were documented. Please discuss any question with your care team.",
  "Meals were recorded on 4 of 7 days in this period (12 meals).",
  "Meals were recorded on 4 of 7 days. Days without a record are unknown, not days without eating.",
  "Average recorded protein_g on days with complete data: 44 g.",
])("localizes generated system text: %s", (source) => {
  setLocale("ar", false);
  expect(tr(source)).not.toMatch(/[a-z]/i);
  setLocale("en", false);
  expect(tr(source)).toBe(source);
});

it("preserves original user-entered records and identifiers", () => {
  setLocale("ar", false);
  expect(tr("SYN-001")).toBe("SYN-001");
  expect(tr("A patient's own English note")).toBe("A patient's own English note");
});

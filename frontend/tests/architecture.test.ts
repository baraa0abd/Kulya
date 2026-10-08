import { readdirSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import ts from "typescript";
import { expect, it } from "vitest";

const root = resolve("src");
function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = resolve(directory, entry.name);
    return entry.isDirectory() ? sourceFiles(file) : /\.tsx?$/.test(file) ? [file] : [];
  });
}
const files = sourceFiles(root);
const known = new Set(files);
const imports = new Map<string, string[]>();
for (const file of files) {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
  );
  const targets: string[] = [];
  for (const statement of source.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier))
      continue;
    const clause = statement.importClause;
    if (clause?.isTypeOnly) continue;
    if (
      clause?.namedBindings &&
      ts.isNamedImports(clause.namedBindings) &&
      !clause.name &&
      clause.namedBindings.elements.every((binding) => binding.isTypeOnly)
    )
      continue;
    const specifier = statement.moduleSpecifier.text;
    if (/\.(css|svg|ico)$/.test(specifier)) continue;
    if (!specifier.startsWith("@/") && !specifier.startsWith(".")) continue;
    const base = specifier.startsWith("@/")
      ? resolve(root, specifier.slice(2))
      : resolve(dirname(file), specifier);
    const target = [base + ".ts", base + ".tsx"].find((candidate) => known.has(candidate));
    if (!target) throw new Error(`Unresolved source import ${specifier} in ${file}`);
    targets.push(target);
  }
  imports.set(file, targets);
}
const short = (file: string) => relative(root, file).replaceAll("\\", "/");

it("keeps shared code independent of feature UI and route entry points", () => {
  const violations = [...imports].flatMap(([file, targets]) =>
    targets
      .filter((target) => {
        const from = short(file),
          to = short(target);
        if (to.startsWith("app/")) return true;
        return (
          (from.startsWith("lib/") || from.startsWith("components/")) && to.includes("/components/")
        );
      })
      .map((target) => `${short(file)} -> ${short(target)}`),
  );
  expect(violations).toEqual([]);
});

it("keeps data contracts and meal rules independent of transport and React", () => {
  for (const file of files.filter((file) => /(?:types|meal-input)\.ts$/.test(file))) {
    const source = ts.createSourceFile(
      file,
      readFileSync(file, "utf8"),
      ts.ScriptTarget.Latest,
      true,
    );
    const dependencies = source.statements
      .filter(ts.isImportDeclaration)
      .map((statement) => (statement.moduleSpecifier as ts.StringLiteral).text);
    expect(
      dependencies.filter((module) => /react|next|\/api$|\/components\//.test(module)),
    ).toEqual([]);
  }
});

it("has no runtime source import cycles", () => {
  const visited = new Set<string>();
  const cycles: string[] = [];
  function visit(file: string, stack: string[]) {
    if (stack.includes(file)) {
      cycles.push([...stack.slice(stack.indexOf(file)), file].map(short).join(" -> "));
      return;
    }
    if (visited.has(file)) return;
    for (const target of imports.get(file) ?? []) visit(target, [...stack, file]);
    visited.add(file);
  }
  files.forEach((file) => visit(file, []));
  expect(cycles).toEqual([]);
});

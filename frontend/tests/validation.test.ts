import { optionalNumber, requiredText } from "@/lib/validation";
import { loginSchema, requiredNumber } from "@/lib/validation";
import { describe, expect, it } from "vitest";

describe("measurement input classes", () => {
  it.each(["", " ", "\t", "abc", "NaN", "Infinity", "-Infinity", undefined, null, true, false])(
    "rejects missing or non-finite required input %j",
    (value) => {
      expect(requiredNumber.safeParse(value).success).toBe(false);
    },
  );
  it.each(["0", "-20", "12.5", " 42 "])("parses real numeric input %j", (value) => {
    expect(requiredNumber.parse(value)).toBe(Number(value));
  });
  it.each(["", null, undefined])("preserves optional missing values %j", (value) => {
    expect(optionalNumber(20, 300).parse(value)).toBeUndefined();
  });
  it.each([20, 300, "20", "300", "64.2"])("accepts inclusive weight boundary %j", (value) => {
    expect(optionalNumber(20, 300).parse(value)).toBe(Number(value));
  });
  it.each([19.99, 300.01, -1, "abc", "Infinity"])("rejects invalid weight %j", (value) => {
    expect(optionalNumber(20, 300).safeParse(value).success).toBe(false);
  });
});

describe("credentials and text", () => {
  it("preserves password spaces and Unicode while normalizing username", () => {
    expect(loginSchema.parse({ username: " nurse1 ", password: " كلمة سر " })).toEqual({
      username: "nurse1",
      password: " كلمة سر ",
    });
  });
  it.each(["", " ", "\n"])("rejects blank required text %j", (value) => {
    expect(requiredText("Note").safeParse(value).success).toBe(false);
  });
  it("rejects empty credentials", () => {
    expect(loginSchema.safeParse({ username: "", password: "" }).success).toBe(false);
  });
  it("keeps arbitrary user content as text", () => {
    expect(requiredText("Note").parse("  <script>alert(1)</script> ملاحظة  ")).toBe(
      "<script>alert(1)</script> ملاحظة",
    );
  });
});

/** Accept the decimal digits commonly typed by Arabic and English speakers. */
export function mealAmount(text: string): number {
  const normalized = text.trim().replace(/[٠-٩]/g, digit => String(digit.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, digit => String(digit.charCodeAt(0) - 0x6f0)).replace(/[٫,]/g, ".");
  return /^\d+(?:\.\d+)?$/.test(normalized) ? Number(normalized) : NaN;
}

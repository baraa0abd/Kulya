import "@testing-library/jest-dom/vitest";

import { setLocale } from "@/lib/i18n";

// Component tests assert on the English source strings; Arabic is covered by its own tests.
setLocale("en", false);

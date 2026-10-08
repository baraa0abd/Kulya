import { z } from "zod";

/** Reject missing measurements instead of coercing them to a real zero. */
export const requiredNumber = z.preprocess(
  (value) => value === null || typeof value === "boolean" || (typeof value === "string" && value.trim() === "") ? undefined : value,
  z.coerce.number({ message: "Enter a number." }),
);

/** Passwords are credentials: surrounding spaces must be preserved. */
export const loginSchema = z.object({
  username: z.string().trim().min(1, "Username is required."),
  password: z.string().min(1, "Password is required."),
});

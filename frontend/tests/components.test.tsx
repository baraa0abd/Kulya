import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { AiLabel, Load, Measurements, optionalNumber, requiredText, Status, Timeline, ZForm } from "@/components/app";
import { ApiError, describeError, type SessionDetail } from "@/lib/api";
import { label, minutesBetween, weekOf, withUnit } from "@/lib/format";
import { setLocale, tr } from "@/lib/i18n";

const session: SessionDetail = {
  id: "s1",
  patient: "p1",
  patient_name: "Synthetic Patient",
  status: "completed",
  scheduled_start: "2026-10-01T08:00:00Z",
  started_at: "2026-10-01T08:00:00Z",
  ended_at: "2026-10-01T11:20:00Z",
  prescribed_duration_minutes: 240,
  pre_weight_kg: "64.0",
  post_weight_kg: null,
  uf_volume_ml: 2000,
  vitals: [
    { id: "v1", kind: "systolic_bp", value: "140.00", unit: "mmHg", phase: "pre", source: "measured", verification_status: "verified", recorded_at: "2026-10-01T08:01:00Z" },
  ],
  device_readings: [],
  nursing_actions: [
    { id: "a1", session: "s1", author_name: "Nurse Demo", action_type: "fluid_bolus", description: "Saline given.", reason: "", performed_at: "2026-10-01T10:00:00Z", amends: null },
  ],
  nursing_notes: [{ id: "n1", author_name: "Nurse Demo", text: "Patient comfortable.", created_at: "2026-10-01T08:30:00Z" }],
  events: [
    { id: "e1", event_type: "hypotension", description: "Low reading.", occurred_at: "2026-10-01T09:55:00Z", resolution: "", resolved_at: null },
  ],
};

describe("formatting", () => {
  it("always shows a unit and never shows a missing value as zero", () => {
    expect(withUnit("64.0", "kg")).toBe("64 kg");
    expect(withUnit(0, "mL")).toBe("0 mL");
    expect(withUnit(null, "kg")).toBe("Not recorded");
    expect(withUnit(undefined, "kg")).toBe("Not recorded");
  });
  it("derives duration and week, and labels codes", () => {
    expect(minutesBetween(session.started_at, session.ended_at)).toBe(200);
    expect(minutesBetween(session.started_at, null)).toBeNull();
    expect(weekOf("2026-10-08T09:00:00Z")).toBe(weekOf("2026-10-05T09:00:00Z"));
    expect(label("action_without_reason")).toBe("Action without reason");
  });
  it("turns API errors into readable text including field messages", () => {
    const error = new ApiError(400, "validation_error", "Invalid input.", { value: ["Outside the plausible range."] });
    expect(describeError(error)).toBe("Invalid input. value: Outside the plausible range.");
    expect(describeError(new Error("x"))).toMatch(/went wrong/);
  });
});

describe("states and labels", () => {
  const base = { reload: vi.fn() };
  it("renders loading, error with retry, empty and data states", async () => {
    const { rerender } = render(<Load from={{ ...base, data: null, error: null, loading: true }}>{() => "data"}</Load>);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    rerender(<Load from={{ ...base, data: null, error: "Not found.", loading: false }}>{() => "data"}</Load>);
    expect(screen.getByRole("alert")).toHaveTextContent("Not found.");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(base.reload).toHaveBeenCalled();
    rerender(<Load from={{ ...base, data: [], error: null, loading: false }} empty="No rows.">{() => "data"}</Load>);
    expect(screen.getByText("No rows.")).toBeInTheDocument();
    rerender(<Load from={{ ...base, data: [1], error: null, loading: false }}>{() => "data"}</Load>);
    expect(screen.getByText("data")).toBeInTheDocument();
  });
  it("labels AI content and review status", () => {
    render(
      <>
        <AiLabel text="AI-generated draft. Advisory only; requires review by an authorized clinician." />
        <Status value="pending_review" />
      </>,
    );
    expect(screen.getByTestId("ai-label")).toHaveTextContent("AI-generated. Advisory only");
    expect(screen.getByText("Pending review")).toBeInTheDocument();
  });
});

describe("clinical widgets", () => {
  it("shows measurements with units and marks missing values", () => {
    render(<Measurements session={session} />);
    expect(screen.getByText("64 kg")).toBeInTheDocument();
    expect(screen.getByText("200 min")).toBeInTheDocument();
    expect(screen.getByText("140 mmHg")).toBeInTheDocument();
    expect(screen.getByText("Not recorded")).toBeInTheDocument(); // post-treatment weight
  });
  it("orders the timeline chronologically and states undocumented reasons and resolutions", () => {
    render(<Timeline session={session} />);
    const items = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(items.map((t) => t.slice(0, 5))).toEqual(["NoteN", "Event", "Actio"]);
    expect(items[1]).toContain("No resolution documented");
    expect(items[2]).toContain("No reason documented");
  });
});

describe("ZForm", () => {
  const schema = z.object({ text: requiredText("Feedback"), amount: optionalNumber(0, 100) });
  const fields = [
    { name: "text", label: "Feedback", type: "textarea" as const },
    { name: "amount", label: "Amount", type: "number" as const },
  ];
  it("blocks invalid input before any request is made", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ZForm schema={schema} fields={fields} submitLabel="Send" onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Amount"), "500");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Feedback is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
  it("submits parsed values and shows a server error", async () => {
    const onSubmit = vi.fn().mockRejectedValueOnce(new ApiError(409, "invalid_state", "Session is completed."));
    render(<ZForm schema={schema} fields={fields} submitLabel="Send" onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Feedback"), "Please clarify");
    await userEvent.type(screen.getByLabelText("Amount"), "12.5");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ text: "Please clarify", amount: 12.5 }));
    expect(await screen.findByText("Session is completed.")).toBeInTheDocument();
  });
});

describe("Arabic interface", () => {
  it("translates labels, statuses and codes, and falls back to the source text", () => {
    setLocale("ar", false);
    try {
      expect(document.documentElement.dir).toBe("rtl");
      expect(document.documentElement.lang).toBe("ar");
      expect(tr("Sign in")).toBe("تسجيل الدخول");
      expect(label("action_without_reason")).toBe("إجراء بلا سبب");
      expect(withUnit(null, "kg")).toBe("غير مسجَّل");
      expect(withUnit("64.0", "kg")).toBe("64 kg"); // values and units are never translated
      expect(tr("Some server text with no entry")).toBe("Some server text with no entry");
      render(<Status value="pending_review" />);
      expect(screen.getByText("بانتظار المراجعة")).toBeInTheDocument();
    } finally {
      setLocale("en", false);
    }
    expect(document.documentElement.dir).toBe("ltr");
  });
});

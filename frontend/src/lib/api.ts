/**
 * Typed client for the Django API. Authorization is decided entirely on the server: this file
 * only attaches the session token and reports what the server said.
 */

export type Role = "doctor" | "nurse" | "patient" | "family" | "org_admin" | "auditor" | "sys_admin";

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  organization: string | null;
}
export interface Patient {
  id: string;
  full_name: string;
  mrn?: string;
  date_of_birth?: string;
}
export type SessionStatus = "scheduled" | "in_progress" | "completed" | "cancelled";
export interface Session {
  id: string;
  patient: string;
  patient_name: string;
  patient_mrn?: string;
  status: SessionStatus;
  scheduled_start: string;
  started_at: string | null;
  ended_at: string | null;
  prescribed_duration_minutes?: number;
  pre_weight_kg?: string | null;
  post_weight_kg?: string | null;
  uf_volume_ml?: number | null;
}
export interface Vital {
  id: string;
  kind: string;
  value: string;
  unit: string;
  phase: string;
  source: string;
  verification_status: string;
  recorded_at: string;
}
export interface DeviceReading {
  id: string;
  kind: string;
  value: string;
  unit: string;
  source: string;
  recorded_at: string;
}
export interface NursingAction {
  id: string;
  session: string;
  author_name: string;
  action_type: string;
  description: string;
  reason: string;
  performed_at: string;
  amends: string | null;
}
export interface NursingNote {
  id: string;
  author_name: string;
  text: string;
  created_at: string;
}
export interface SessionEvent {
  id: string;
  event_type: string;
  description: string;
  occurred_at: string;
  resolution: string;
  resolved_at: string | null;
}
export interface SessionDetail extends Session {
  vitals: Vital[];
  device_readings: DeviceReading[];
  nursing_actions: NursingAction[];
  nursing_notes: NursingNote[];
  events: SessionEvent[];
}
export interface Finding {
  finding_id: string;
  check: string;
  description: string;
  source_record_ids: string[];
}
export interface ProtocolPassage {
  id: string;
  title: string;
  protocol_version: string;
  section: string;
  similarity: number;
  is_synthetic: boolean;
}
export interface AIError {
  code: string;
  message: string;
}
export interface AIReview {
  id: string;
  session: string;
  status: "processing" | "pending_review" | "ai_unavailable" | "reviewed";
  label: string;
  rule_findings: Finding[];
  protocol_passages: ProtocolPassage[];
  output: {
    summary: string;
    documentation_gaps: { finding_id: string; description: string; protocol_reference_ids: string[] }[];
    protocol_discrepancies: { description: string }[];
    questions_for_doctor: string[];
  } | null;
  ai_error: AIError[];
  model_name: string;
  created_at: string;
}
export interface Metric {
  value: number | null;
  unit: string;
  kind: string;
}
export interface AISummary {
  id: string;
  session: string;
  version: number;
  status: "processing" | "unverified" | "verified" | "rejected" | "ai_unavailable";
  label: string;
  metrics: Record<string, Metric>;
  output: {
    clinical_summary: string;
    patient_summary: string;
    documented_events: string[];
    nursing_actions: string[];
    missing_information: string[];
  } | null;
  ai_error: AIError[];
  released: boolean;
  created_at: string;
}
export interface ReleasedSummary {
  id: string;
  session: string;
  session_date: string;
  patient_name: string;
  text: string;
  released_at: string;
}
export interface ReviewTask {
  id: string;
  session: string;
  session_date: string;
  patient: string;
  patient_name: string;
  ai_review: string | null;
  review_status: string | null;
  finding_count: number;
  status: "open" | "done";
}
export interface Feedback {
  id: string;
  session: string;
  author_name: string;
  kind: "feedback" | "clarification_request";
  text: string;
  nursing_action: string | null;
  created_at: string;
}
export interface Notification {
  id: string;
  kind: string;
  title: string;
  session: string | null;
  read_at: string | null;
  created_at: string;
}
export interface LabResult {
  id: string;
  analyte: string;
  value: string;
  unit: string;
  reference_low: string | null;
  reference_high: string | null;
}
export interface LabReport {
  id: string;
  patient: string;
  collected_at: string;
  released_to_patient: boolean;
  results: LabResult[];
}
export interface Prescription {
  id: string;
  version: number;
  duration_minutes: number;
  blood_flow_ml_min: number | null;
  target_uf_ml: number | null;
  access_type: string;
  active: boolean;
}
export interface Consent {
  id: string;
  patient_name: string;
  caregiver_name: string;
  scopes: string[];
  expires_at: string | null;
  revoked_at: string | null;
}
interface Page<T> {
  count: number;
  results: T[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = {},
  ) {
    super(message);
  }
}

const KEY = "copilot.session";
type Tokens = { access: string; refresh: string };

// sessionStorage: scoped to this tab and gone when it closes. Never localStorage.
function tokens(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as Tokens) : null;
}
function store(value: Tokens | null) {
  if (value) window.sessionStorage.setItem(KEY, JSON.stringify(value));
  else window.sessionStorage.removeItem(KEY);
}

async function send(path: string, init: RequestInit, access?: string): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);
  return fetch(`/api${path}`, { ...init, headers });
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let current = tokens();
  let response = await send(path, init, current?.access);
  if (response.status === 401 && current) {
    // Access tokens are short-lived: refresh once, then replay.
    const refreshed = await send("/auth/refresh/", {
      method: "POST",
      body: JSON.stringify({ refresh: current.refresh }),
    });
    if (refreshed.ok) {
      current = { ...current, access: ((await refreshed.json()) as { access: string }).access };
      store(current);
      response = await send(path, init, current.access);
    } else {
      store(null);
    }
  }
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code: string; message: string; details: unknown } } | null)?.error;
    throw new ApiError(response.status, error?.code ?? "error", error?.message ?? "Request failed.", error?.details);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  /** First page (50 rows) of a paginated list. */
  list: async <T>(path: string) => (await request<Page<T>>(path)).results,
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  async login(username: string, password: string): Promise<User> {
    const data = await request<Tokens & { user: User }>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    store({ access: data.access, refresh: data.refresh });
    return data.user;
  },
  logout: () => store(null),
  hasSession: () => tokens() !== null,
};

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const details = error.details && typeof error.details === "object" ? Object.entries(error.details) : [];
    const fields = details.map(([field, messages]) => `${field}: ${[messages].flat().join(" ")}`).join(" · ");
    return fields ? `${error.message} ${fields}` : error.message;
  }
  return "Something went wrong. Please try again.";
}

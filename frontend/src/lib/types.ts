/**
 * Shared API data contracts. No transport, browser state or UI belongs in this module.
 */

export type Role =
  "doctor" | "nurse" | "patient" | "family" | "dietitian" | "org_admin" | "auditor" | "sys_admin";

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

type SessionStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

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

interface ProtocolPassage {
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
    documentation_gaps: {
      finding_id: string;
      description: string;
      protocol_reference_ids: string[];
    }[];
    protocol_discrepancies: { description: string }[];
    questions_for_doctor: string[];
  } | null;
  ai_error: AIError[];
  model_name: string;
  created_at: string;
}

interface Metric {
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
  patient?: string | null;
  read_at: string | null;
  created_at: string;
}

interface LabResult {
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

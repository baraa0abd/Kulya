# Architecture

```
Browser ── Next.js (dashboards, /api proxy) ── Django REST API ── PostgreSQL 16 + pgvector
                                                   │
                                                   └─ Celery worker ── Redis (broker)
                                                          └─ LLM provider (Claude API or offline mock)
```

The browser only talks to the Next.js origin; `/api/*` is proxied to Django. All authorization is
decided in Django.

## Backend apps

| App | Owns |
|---|---|
| `core` | Organization, User (roles), AuditEvent, IdempotencyKey, authorization policy, error format |
| `clinical` | Patient, CareAssignment, CaregiverConsent, DialysisDevice, DialysisPrescription, DialysisSession, VitalSign, DeviceReading, LaboratoryReport/Result, NursingAction, NursingNote, SessionEvent |
| `ai` | ClinicalProtocol, ProtocolVersion, ProtocolChunk (pgvector), AIReview, AISummary, rules, retrieval, provider adapters, validation, Celery tasks |
| `workflow` | DoctorFeedback, ReviewTask, Notification |
| `nutrition` | FoodItem, Recipe, MealLog, MealComponent, MealMedia, NutrientEstimate, NutritionPlan, MealRecommendation, FoodLabReview, NutritionReport, NutritionObservation, nutrient engine, USDA client |

Views are thin. Anything that writes lives in a `services.py` and writes an audit event.

## Data rules

- UUID primary keys and timezone-aware timestamps everywhere (`core.models.UUIDModel`).
- Measurements store value, unit, source and verification status. One unit per kind; a different
  unit is rejected, never converted.
- Signed records (vitals, device readings, nursing actions, notes, doctor feedback, audit events)
  are immutable: no update or delete endpoint exists and the model refuses both. A correction is a
  new row with `amends` pointing at the original.
- Prescriptions are versioned; a session keeps the version it was run under.
- Database constraints: one open review task per session; a summary cannot be released unless
  verified; a session cannot end before it starts; unique MRN per organization.

## Authorization

Default deny, two layers, both on the server (`core/permissions.py`):

1. `RolePolicy`: each view declares which roles may read, write, or call each action. A view that
   declares nothing is closed.
2. `patients_for(user)`: every queryset is filtered to the caller's patients first.
   - doctor / nurse: same organization **and** an active care assignment
   - patient: their own record
   - family: patients with an unexpired, unrevoked consent grant, per scope
     (`summaries`, `appointments`, `labs`)
   - admin, auditor, service roles: no clinical data

A record outside the caller's scope returns 404. The client's idea of its role is never used.

## Feature 1: AI nursing documentation review

Trigger: a nursing action is submitted, a session is completed, or a doctor requests reanalysis.

1. The clinical write commits. Then a Celery task is queued; if the broker is down the write
   still succeeds and the failure is logged.
2. `ai.context.build_context`: de-identified session context (ids only, no names) plus metrics
   calculated in backend code.
3. `ai.rules.run_checks`: seven deterministic documentation checks (pure functions).
4. `ai.rag.retrieve`: approved, in-date protocol passages of the same organization from pgvector.
   Nothing similar enough → `protocol_reference_unavailable` / `insufficient_protocol_evidence`.
5. Provider call with the versioned prompt `review_v1`. Record text is passed as data.
6. `ai.validation.validate_review`: strict JSON schema; `requires_human_review` must be true;
   every cited record id must be in the context; every cited passage id must have been retrieved;
   wording that diagnoses, prescribes, grades staff or instructs machine operation is rejected.
7. Result stored as `AIReview`: `pending_review` (valid draft) or `ai_unavailable` (provider
   failed or output rejected — rule findings are kept, and the error is recorded).
8. One open `ReviewTask` per session; assigned doctors are notified. Doctor feedback closes the
   review and notifies the nurses.

Idempotency: the review key is a hash of session, trigger and record fingerprint, so a redelivered
task creates nothing new.

## Feature 2: AI session summaries

Generated on session completion or on request. Prompt `summary_v1`. Validation: schema;
`treatment_duration_minutes` must equal the backend calculation; cited ids must exist; every
number in the prose must be an actual value in the structured records (a number that only appears
in a free-text note is not accepted as a measurement); same forbidden-wording net.

Lifecycle: `unverified` → doctor `verified` or `rejected` → doctor `release`. Patients and
caregivers only ever receive the `patient_summary` text of a verified and released summary.

## Providers and retrieval

- `AnthropicProvider`: Claude API, model from `LLM_MODEL` (default `claude-opus-5-5`), timeout and
  two SDK retries, no tools, no sampling parameters.
- `MockProvider`: offline template that composes schema-valid output from the structured input.
  Used in tests, seeding and the default demo. It is not a language model.
- Embeddings: `HashingEmbedder`, a deterministic 256-dimension lexical hash. It needs no network,
  but it matches words, not meaning. Replace it behind `ai.rag.get_embedder` for real retrieval.
- Protocols: one clearly labelled **synthetic** workflow policy (`backend/ai/protocols/`). No
  clinician-approved protocol is included.

## Frontend

Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, Recharts, React Hook Form + Zod.
`src/lib/api.ts` is the typed client; `src/components/app.tsx` holds the shared widgets
(loading/error/empty states, forms, timeline, measurements, lab trends, notifications).

| Route | Role | Content |
|---|---|---|
| `/doctor/` | doctor | pending reviews, assigned patients, nursing activity, notifications |
| `/doctor/patients/[id]/` | doctor | session history, lab trends and release, dialysis orders |
| `/doctor/sessions/[id]/` | doctor | measurements, AI review, AI summary verify/release, timeline, feedback |
| `/nurse/` | nurse | today's schedule, assigned patients, scheduling, feedback inbox |
| `/nurse/sessions/[id]/` | nurse | start/complete, vitals, actions, readings, events, notes, completeness |
| `/patient/` | patient, family | released summaries, sessions, lab trends, family sharing, home measurements |

Route guards in the browser are navigation convenience only; the API enforces access.

Visual design: the "Dialysis Clinical Intelligence" design system. Tokens and component styling
live in `src/app/globals.css` (petrol-blue primary, jade for stable states, periwinkle reserved for
AI content, 1px borders, 4px controls, 8px cards, Inter + Noto Sans Arabic, tabular numerals). The
frame is a side rail with section navigation plus a sticky top bar; dashboards open with a row of
key figures; session screens use a main column with an AI / review rail. Every figure and
navigation item is backed by real data or a real section: the design mock-ups' machine telemetry,
chair numbers and phone lines are not shown because the system has no such data.

Language: `src/lib/i18n.tsx` holds an English-to-Arabic dictionary keyed by the English source
string. Arabic (RTL) is the default; the choice is kept in `localStorage`. Missing entries fall
back to English. Dates use Arabic month names with Latin digits; values and units are never
translated.

## API

Groups under `/api/`: `auth`, `patients`, `care-assignments`, `consent`, `prescriptions`,
`sessions`, `nursing-actions`, `nursing-notes`, `device-readings`, `session-events`, `vitals`,
`labs`, `ai/reviews`, `ai/summaries`, `doctor/feedback`, `doctor/review-tasks`, `notifications`,
`audit`, `health`. Paginated lists (50 per page), `?ordering=`, per-resource filters, one error
shape `{"error": {"code", "message", "details"}}`, rate limits, `Idempotency-Key` on session and
record creation. Full schema: `docs/openapi.yaml` or `/api/docs/`.

## Renal nutrition (`backend/nutrition`)

Same pattern as the two session features: deterministic code produces the facts, the model only
proposes or describes, strict validation rejects anything else, and a clinician reviews before a
patient sees AI-written text.

| Step | Where | Deterministic or AI |
|---|---|---|
| Nutrient totals of a meal | `engine.estimate` (catalogue value per 100 g x grams) | Deterministic. Client-sent values are ignored. |
| Diary averages, missing days | `engine.diary_summary` | Deterministic. Average over days with complete data only. |
| Recipe versus plan | `engine.classify_recipe` | Deterministic. Limits come only from the clinician's plan. |
| What was eaten (text, speech, photo) | `services.recognize`, prompt `nutrition_recognize_v1` | AI proposes names and portions; the person confirms each line; nothing is saved before that. |
| Food and lab review | `services.analyze`, prompt `nutrition_analyze_v1` | AI describes side by side; draft until a doctor or dietitian approves. |
| Suggestion wording | `services.suggest`, prompt `nutrition_suggest_v1` | AI words the rule result; pending until approved. |
| Report narrative | `services.build_report`, prompt `nutrition_report_v1` | AI draft stored apart from the facts; released by a clinician. |

Rules that hold everywhere:

- An unknown nutrient is `null`, never 0. A day without a record is "not recorded", never "ate nothing".
- The model never outputs a nutrient number, a limit or a plan. `NutritionPlan` rows are created
  only by `approve_plan`, called by a doctor or dietitian; each save is a new version.
- `nutrition/ai.py` rejects output with causal wording ("caused", "due to", ...), any mention of
  creatinine, medication or supplement advice, instructions to the patient, numbers that are not
  values in the input, and citations of results that were not provided. A rejected or failed call
  leaves the deterministic facts in place and marks the draft `ai_unavailable`.
- Photos are resized in the browser, sent once for recognition and not stored. `MealMedia` records
  only that a photo or voice clip was used.
- Idempotency: reviews and reports are keyed by a SHA-256 fingerprint of their input; suggestions
  are created once per recipe and plan version.

Roles: `dietitian` reaches patients through `CareAssignment` like other staff and has no access to
session documentation. Doctors and dietitians approve plans, review drafts and release reports;
nurses read the diary and record observations; patients write their own diary; a family caregiver
needs the `nutrition` consent scope to read and `nutrition_log` to record meals.

Frontend: `src/components/nutrition.tsx` holds every panel. Routes are thin: `/patient/nutrition/`
(+ `add`, `history`, `suggestions`, `labs`, `reports`), `/doctor/patients/[id]/nutrition/`
(+ `lab-review`, `reports`; also used by dietitians and nurses), `/dietitian/`.

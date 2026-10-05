# Architecture

```
Flutter web app ──HTTP/JSON──> Django REST API (/api/v1) ──> PostgreSQL
                                   │
                                   ├─ clinical   sessions, notes (immutable), SessionFacts
                                   ├─ ai_engine  prompts, schemas, LLM clients, validators, drafts
                                   ├─ rules      deterministic flags R1–R6
                                   ├─ summaries  cited summaries, doctor approval
                                   ├─ audit      who did what, before/after
                                   └─ seed       synthetic demo data
```

Views are thin. Anything that writes the record is a function in an app's `services.py`.

## The three kinds of data

| Kind | Source | Trust |
|---|---|---|
| Vitals (`Session`) | typed by a nurse into numeric fields | record |
| Notes (`Note`) | typed by a nurse, immutable | record |
| Drafts (`ExtractionDraft`, `Summary` in draft) | the model | **not** the record until a human approves |

`SessionFacts` and `Flag` are derived: facts only from nurse-approved drafts, flags only from
vitals + approved facts through pure functions.

## Request flow: a note

1. `POST /sessions/{id}/notes/` → `clinical.services.create_note` saves the note and commits.
2. `ai_engine.services.request_extraction` calls the model, then `validate_extraction`.
   Valid → draft `pending`. Anything else (bad JSON, schema error, ungrounded span, network error,
   refusal) → draft `invalid` with `validation_errors`. It never raises, so the note is always saved.
3. A nurse opens the draft. `approve` (optionally with an edited payload, which is re-validated)
   → `merge_facts` writes `SessionFacts` → audit row → `rules.services.evaluate_patient` recomputes
   that patient's flags in the same transaction.

## AI pipeline

### Versions

| Artifact | Version | File |
|---|---|---|
| Extraction prompt | `extraction_v1` | `backend/ai_engine/prompts/extraction_v1.md` |
| Clinician summary prompt | `summary_clinician_v1` | `backend/ai_engine/prompts/summary_clinician_v1.md` |
| Patient summary prompt | `summary_patient_v1` | `backend/ai_engine/prompts/summary_patient_v1.md` |
| Extraction schema | `extraction_v1` | `backend/ai_engine/schemas/extraction_v1.json` |
| Summary schema | `summary_v1` | `backend/ai_engine/schemas/summary_v1.json` |

Each draft and summary stores `prompt_version` and `model_name`. To change a prompt or schema, add a
`_v2` file; do not edit a version that has produced stored drafts.

### What the model receives

- **Extraction:** the prompt as system text, and the note wrapped in `<note>…</note>`. Nothing else.
- **Summary:** the prompt, and one JSON document in `<data>…</data>` built by
  `summaries.services.build_summary_input`: synthetic patient code, the period, and for each session
  that has a note with an approved extraction — its typed vitals, its approved facts, and the note
  ids. Rule flags are included with their message and note ids. No names, no raw note text, nothing
  from pending, rejected, or invalid drafts.

### Validation (`ai_engine/validators.py`)

1. Parse JSON (code fences stripped); must be an object.
2. JSON Schema, `additionalProperties: false`, closed enums, length limits.
3. Extraction: every `evidence_span`, `raw_text`, and `uncertain.text` must be a substring of the
   note after `normalize_ar` on both sides.
4. Summary: every sentence has ≥ 1 citation; every citation is one of the note ids that were sent;
   no sentence contains a term from `ai_engine/forbidden_terms.py`.
5. Only output that passes everything becomes `pending` (extraction) or `draft` (summary).

The forbidden-terms list is a blunt substring net, not a classifier. It will miss novel advice
phrasings and can reject an innocent sentence; the doctor's review is the real control.

### Clients

`get_llm_client()` returns `MockLLMClient` for `LLM_PROVIDER=mock`, and `AnthropicLLMClient` for
`anthropic` — unless `ANTHROPIC_API_KEY` is empty, in which case it logs a warning and returns the
mock so the demo keeps working.

- `AnthropicLLMClient`: model from `LLM_MODEL` (default `claude-opus-5-5`), timeout
  `LLM_TIMEOUT_SECONDS` (30), 2 SDK retries with backoff, effort from `LLM_EFFORT` (`low`). No
  `temperature`: current models reject it.
- `MockLLMClient`: `tests/fixtures/llm/{prompt_id}/{sha256(user_input)[:12]}.json`, then
  `default.json`, then for summary prompts a deterministic template summary.

### Evaluation

`eval/golden/golden.json` holds 20 synthetic Iraqi-dialect notes with hand-written expected
extractions (negation, past events, spelling variants, Arabic-Indic digits, access findings,
uncertain statements). `eval/run_eval.py` scores `symptoms` and `access_findings` by code per note
and reports precision, recall, invalid rate, and evidence failures to `eval/report.md`.

**Current results:** only the mock sanity run exists (precision = recall = 1.00, which proves the
harness, not the model). No real-model run has been done; the targets below are unmeasured.

| Target (real model) | Value |
|---|---|
| Symptom recall | ≥ 0.85 |
| Symptom precision | ≥ 0.90 |
| Accepted drafts with ungrounded spans | 0 (guaranteed by the validator) |
| Invalid rate | ≤ 10% |

## Rules engine

`rules/engine.py` holds R1–R6 as pure functions over `SessionSnapshot` dataclasses; `now` is an
argument. `rules/services.evaluate_patient` builds snapshots from the ORM, runs every rule, and
replaces the patient's flags in one transaction. Thresholds live in `rules/config.yaml`, validated
with pydantic; each flag stores the config hash as `rules_version`. Thresholds are demo
placeholders, not clinical guidance (`docs/clinical_disclaimer.md`).

## Access control

Role permission classes in `accounts/permissions.py`, plus queryset scoping so that anything a
patient may not see returns 404. A patient can reach exactly two things: their own `Patient` row and
approved patient-audience summaries of their own record.

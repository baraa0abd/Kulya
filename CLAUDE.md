# Kulya (كُلية) — instructions for every Claude Code session

Kulya helps dialysis nurses and nephrologists review a patient across repeated sessions: structured vitals,
Arabic free-text notes, AI extraction drafts a nurse approves, deterministic rule flags, and cited summaries a
doctor approves. Full detail (data model, API contract, AI contracts, rules, role prompts):
`docs/team_prompts.json`. Current state and deviations: `HANDOFF.md`.

## Non-negotiables (verbatim from shared_context — never weaken these)

1. **AI never writes to the clinical record directly. All AI output is stored as a draft with status 'pending' until a human approves or rejects it.**
   Why: Clinical safety and accountability. A wrong AI extraction must be caught by a person before it becomes part of the record.
2. **AI never enters, changes, or calculates numeric vitals, and never decides what is abnormal. Numbers come from typed fields; patterns come from the rules engine.**
   Why: Language models can misread or invent numbers. Deterministic code is testable and explainable; that is what judges and clinicians will trust.
3. **AI never suggests diagnoses, medication, or treatment changes. Summaries describe only what was documented.**
   Why: The project's scope is documentation and review support, not clinical decision-making. Crossing that line creates medical and regulatory risk.
4. **Every extracted item must include an evidence span that appears verbatim in the source note. Every summary sentence must cite at least one note ID from its input. Outputs failing these checks are rejected automatically.**
   Why: This is the anti-hallucination guarantee. It lets staff click from any claim back to the original words.
5. **Only synthetic patient data is used. Every Patient row has is_synthetic=true and the app refuses to start in DEMO_MODE if any patient is not synthetic.**
   Why: The challenge demo must not contain real health data. This is both an ethical requirement and an easy question to answer in the interview.
6. **The original Arabic note text is immutable once saved. Corrections are new notes that reference the old one.**
   Why: Clinical records must preserve history. It also keeps citation links stable.
7. **All tests must run offline with a mock LLM client. No test may require an API key.**
   Why: Tests must be fast, free, deterministic, and runnable in CI and on the demo machine without internet.

## Repo structure (each role edits only its own folders)

- `backend/` — Django project 'kulya' with apps: accounts, clinical, ai_engine, rules, summaries, audit, seed
- `backend/ai_engine/prompts/` — Versioned prompt files: extraction_v1.md, summary_clinician_v1.md, summary_patient_v1.md
- `backend/ai_engine/schemas/` — JSON Schemas: extraction_v1.json, summary_v1.json
- `backend/tests/fixtures/llm/` — Recorded mock LLM responses used by MockLLMClient
- `backend/seed/data/` — Synthetic patients, sessions, and Arabic notes
- `frontend/` — Flutter app 'kulya_app'
- `docs/` — team_prompts.json, architecture.md, api.md (generated), demo_script.md, clinical_disclaimer.md
- `eval/` — Golden set of annotated synthetic notes and the extraction evaluation script
- `CLAUDE.md` — Repo-level instructions every Claude Code session reads first
- `backend/kulya/common/` — shared helpers: `arabic.normalize_ar`, `errors` (error_format), `stubs`
- `HANDOFF.md` — what exists, what is stubbed, deviations from the contract

## Commands

- `make setup` — install deps, migrate, `flutter pub get`
- `make test` — backend pytest (mock LLM, offline) + `flutter test`. **Must be green before any commit.**
- `make lint` — ruff + black --check + flutter analyze
- `make docs` — regenerate `docs/api.md` from the OpenAPI schema
- No `make` (Windows)? Run the same commands from the Makefile by hand inside `backend/` and `frontend/kulya_app/`.

## Coding standards

- Backend: ruff + black, type hints on all public functions, no business logic in views (use services.py per app).
- Frontend: flutter analyze with zero warnings, feature-first folders, all user-facing strings in ARB files (ar default, en secondary).
- Every Arabic string compared in code goes through the shared normalize_ar() helper.
- Commits: conventional commits (feat:, fix:, test:, docs:). One task = one commit minimum.
- No secrets in code. Use .env and .env.example.

## Definition of done

- All listed tests for the task exist and pass via 'make test'.
- No lint errors (ruff, flutter analyze).
- Endpoints documented in OpenAPI and match api_contract.
- Audit log written for every state change.
- User-visible text available in Arabic with correct RTL layout.
- Works with MockLLMClient offline and with the real LLM when LLM_PROVIDER=anthropic.

## Contract changes

The data model and API paths are frozen. `tests/test_lead.py::test_l_t7...` fails if the OpenAPI paths differ
from `api_contract`. To change a contract: update `docs/team_prompts.json`, the code, `docs/api.md`
(`make docs`), and note it in `HANDOFF.md` so every role sees it.

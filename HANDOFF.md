# HANDOFF

Status: **M0, M1, M2 done; M3 (frontend) done as a single-screen dashboard** on `main`. Next: qa + devops (M4).

- Endpoint reference: `docs/api.md` (generated). Real request/response examples for every endpoint:
  `docs/api_examples.md`.
- Demo data and expected flags: `docs/demo_data.md`. AI pipeline: `docs/architecture.md`.
- Tests: `cd backend && python -m pytest -q` → 90 passing, offline, no API key.

## Endpoint status (all implemented)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/api/v1/auth/token` | anyone | returns `access`, `refresh`, `role`, `patient_id`; `role` is also a JWT claim |
| POST | `/api/v1/auth/token/refresh` | anyone | |
| GET | `/api/v1/patients/` | nurse, doctor | paginated; includes `attention_flag_count` |
| GET | `/api/v1/patients/{id}/` | nurse, doctor, own patient | another patient's id → 404 |
| GET | `/api/v1/patients/{id}/timeline/` | nurse, doctor | newest first; each row = session + `notes` + `facts` (null until an approval) + `flags` |
| POST | `/api/v1/patients/{id}/sessions/` | nurse | 201; typo-guard ranges; `end_time > start_time` |
| GET | `/api/v1/sessions/{id}/` | nurse, doctor | |
| POST | `/api/v1/sessions/{id}/notes/` | nurse | 201; returns note + `draft_id` + `draft_status`; optional `supersedes` |
| GET | `/api/v1/notes/{id}/` | nurse, doctor | notes have no update/delete endpoint |
| GET | `/api/v1/extraction-drafts/?status=` | nurse | `status` optional: pending / approved / rejected / invalid |
| GET | `/api/v1/extraction-drafts/{id}/` | nurse | includes `note_text_ar` for highlighting |
| POST | `/api/v1/extraction-drafts/{id}/approve/` | nurse | optional `edited_payload`; only from `pending`; else 409 |
| POST | `/api/v1/extraction-drafts/{id}/reject/` | nurse | optional `reason`; from `pending` or `invalid` |
| POST | `/api/v1/extraction-drafts/{id}/retry/` | nurse | 201; returns a **new** draft; not allowed once approved |
| GET | `/api/v1/patients/{id}/flags/` | nurse, doctor | |
| POST | `/api/v1/patients/{id}/summaries/` | nurse, doctor | 201; body `audience`, `period_start`, `period_end` |
| GET | `/api/v1/summaries/{id}/` | nurse, doctor; patient if own + approved + patient audience | otherwise 404 for patients |
| POST | `/api/v1/summaries/{id}/approve/` | doctor | only from `draft`; else 409 |
| POST | `/api/v1/summaries/{id}/reject/` | doctor | optional `reason`; only from `draft` |
| GET | `/api/v1/me/summaries/` | patient | approved patient-audience summaries of own record only |
| GET | `/api/v1/audit/?object_type=&object_id=` | admin, doctor | newest first |

Conventions for the frontend:

- Every list is paginated: `{count, next, previous, results}`, 20 per page, `?page=N`.
- Every error is `{"error": {"code", "message_ar", "message_en", "details"}}`. Show `message_ar`.
  Codes in use: `validation_error` (field errors in `details`), `invalid_edit`
  (`details.validation_errors`), `invalid_state` (409), `invalid_supersedes`, `not_authenticated`,
  `authentication_failed`, `permission_denied`, `not_found`.
- Wrong role → 403. Not logged in → 401. A record the user may not know about → 404.
- Decimals (`pre_weight_kg`, `post_weight_kg`) come back as strings, e.g. `"62.9"`.

## What each role delivered

### Lead (M0)

Scaffold, all models + migrations, `normalize_ar`, shared error format, `LLMClient` interface,
`CLAUDE.md`, CI workflow, Flutter app shell (still the `flutter create` template).

### AI (M2)

- Schemas `ai_engine/schemas/{extraction_v1,summary_v1}.json`; prompts
  `ai_engine/prompts/{extraction_v1,summary_clinician_v1,summary_patient_v1}.md`.
- `ai_engine/validators.py`: `validate_extraction(payload, note_text)`,
  `validate_summary(payload, allowed_note_ids)` → `(ok, [{code, path, message}])`.
  Error codes: `schema_invalid`, `evidence_not_found`, `missing_citation`, `unknown_citation`,
  `forbidden_advice`, plus `llm_output_error` / `llm_error` recorded by the services.
- `ai_engine/client.py`: `AnthropicLLMClient`, `MockLLMClient`, `get_llm_client()`.
- `ai_engine/services.request_extraction(note_id)`, `summaries/services.generate_summary(...)`.
- `eval/golden/golden.json` (20 notes), `eval/run_eval.py`, `eval/report.md`.

### Rules + data (M1)

- `rules/config.yaml` + `rules/config.py`; `rules/engine.py` (pure R1–R6);
  `rules/services.evaluate_patient(patient_id)`.
- `seed/data/demo.json` (built by `seed/data/build_demo_data.py`), `manage.py seed_demo [--approve-facts]`.
- `docs/demo_data.md`, `docs/clinical_disclaimer.md`.

### Backend (M1)

- `accounts/permissions.py` (`IsNurse`, `IsDoctor`, `IsClinician`, `IsAdmin`, `IsAuditor`, `IsPatientOwner`).
- `clinical/services.py`: `create_session`, `create_note`, `approve_draft`, `reject_draft`,
  `retry_draft`, `merge_facts`. `summaries/services.py`: `request_summary`, `review_summary`.
- `audit/services.log(actor, action, obj, before, after)`. Actions written: `create_session`,
  `create_note`, `create_extraction_draft`, `approve_draft`, `edit_and_approve_draft`,
  `reject_draft`, `retry_extraction`, `create_summary`, `approve_summary`, `reject_summary`.
- Demo guard in `clinical/apps.py`.

### Frontend (M3) — single-screen dashboard

Built at the product owner's request as **one screen per role** instead of separate routed pages:

- **Staff dashboard** (`lib/dashboard.dart`): patient list with attention-flag counts | SBP chart
  (`fl_chart`, flagged sessions marked) + session cards newest first (vitals, approved facts, rule
  flags with evidence, original notes) | work panel with tabs: draft review, new session, summaries.
  Doctors get the summaries tab only; nurses get all three.
- **Draft review** (`lib/drafts.dart`): original note with every evidence span highlighted, items
  as chips (tap = focus its evidence, × = remove before approving → sent as `edited_payload`),
  mentioned-values warning box, approve / reject / retry; invalid drafts show errors and no approve.
- **Session entry** (`lib/session_form.dart`): Arabic-Indic or Latin digits, inline typo-guard
  ranges mirrored from the backend, optional note posted right after the session.
- **Summaries** (`lib/summaries.dart`): request by audience + period, sentences with citation
  chips that open the source note, doctor approve / reject.
- **Patient screen**: only approved patient-audience summaries (filtered again client-side), large
  text, fixed footer line.
- All strings in `lib/l10n/app_ar.arb` (default) and `app_en.arb`; locale fixed to `ar`, full RTL.
- Tests: `flutter test` → 10 passing (logic + widget tests covering F-T1, 5, 6, 7, 8, 9, 11, 12).

Run it: `cd frontend/kulya_app && flutter build web`, then start the backend with
`DJANGO_DEBUG=true`; Django serves the build at `http://localhost:8000/` (same origin as the API,
so no CORS). In docker, nginx should serve `build/web` and proxy `/api` instead.

Frontend deviations and gaps:

- **No go_router, no Riverpod.** One screen per role chosen by sign-in state needs no router, and a
  single `ChangeNotifier` (`lib/state.dart`) holds the state. Both packages were left out.
- **No bundled Arabic font.** Flutter web fetches Noto fonts from Google at runtime, so Arabic
  glyphs need internet on first load. Bundle Noto Naskh Arabic / Cairo before an offline demo.
- **Staff cannot list existing summaries**: the API contract has no list endpoint for them, so the
  panel shows only summaries requested since sign-in. A doctor cannot find a draft a nurse
  requested earlier. Fixing this needs a contract change (`GET /patients/{id}/summaries/`).
- **Drafts panel is not filtered by patient** (the draft payload has no patient id); it lists every
  pending and invalid draft with its session number.
- Tokens are kept in memory only: reloading the page signs out.
- Below ~1180 px width the dashboard scrolls sideways rather than reflowing.
- Not covered by tests: F-T2 (no routes exist), F-T3/F-T4 (chart and flag card), F-T10 (citation
  sheet). No audit-log screen. No screenshots in `docs/screens/` yet.

## For the next roles

**Frontend.** Build against `docs/api.md` + `docs/api_examples.md`. Log in as `nurse1` / `doctor1` /
`patient_syn001` after `seed_demo`. `GET /extraction-drafts/{id}/` gives `note_text_ar` and `payload`;
highlight every `evidence_span` / `raw_text` / `uncertain.text` in the note (compare after the same
normalisation as `normalize_ar`, or highlight by substring search on the raw text first). When
`edited_payload` is not null it is what was approved. The patient closing line
«ناقش أي سؤال مع فريقك الطبي» is **not** in summary sentences; render it as the fixed footer.

**QA.** Mock fixtures: `tests/conftest.py::mock_llm(prompt_id, response, note_text=...)`. With the
mock, a note with no fixture gets an all-empty (valid) extraction, and summaries with no fixture are
built from a deterministic template (`ai_engine.client.offline_summary`). Seed fixture for tests:
`call_command("seed_demo", "--approve-facts")` with `DEMO_PASSWORD` set.

**DevOps.** Env vars: `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`,
`DEMO_MODE`, `DEMO_PASSWORD`, `LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY`, `LLM_EFFORT`,
`LLM_TIMEOUT_SECONDS`. `LLM_PROVIDER=anthropic` with no key already logs a warning and falls back to
the mock (test `a_t12c`). The mock reads `backend/tests/fixtures/llm/` at runtime, so the image must
ship that folder. Add `gunicorn` to `requirements.txt`. `seed_demo` fails fast without `DEMO_PASSWORD`.

## Deviations from shared_context (with reasons)

1. **Six required vitals are nullable** in the DB and the API. Rule R3 and the SYN-003 storyline
   need incomplete sessions to exist. The entry form may still require them.
2. **`SessionFacts` is one row per session** with three JSON lists; items carry `note_id` + `evidence_span`.
3. **Added fields:** `Summary.created_at`; `Patient.attention_flag_count` (list/detail);
   `draft_id` + `draft_status` on the note-creation response; `note_text_ar` + `session` on drafts;
   `role` + `patient_id` on the token response.
4. **Auth paths have no trailing slash**, exactly as written in `api_contract`.
5. **No `temperature=0`.** Task A4 asks for it, but current Claude models reject sampling parameters
   with a 400. Nothing relies on determinism; every output goes through the validators.
   `LLM_EFFORT` (default `low`) is the tuning knob instead. Default model when `LLM_MODEL` is empty:
   `claude-opus-5-5`.
6. **Patient closing line is not model output.** A6 says the patient summary "ends with" the line,
   but every sentence must carry a citation and a closing remark has none. The prompt tells the
   model the app shows it; the frontend renders it as a fixed footer (task F6 already asks for one).
7. **`mentioned_values[].note`** in `ai_contracts` is treated as documentation, not a field. Items
   are `{kind, raw_text}`.
8. **`uncertain[].text` is also evidence-checked** (the contract calls it a verbatim substring).
9. **Summaries cite only notes with an approved extraction.** Sessions without one are left out of
   the model input entirely, since nothing in them could be cited.
10. **Reject is allowed from `invalid` as well as `pending`** (B4 says pending only; F4 needs
    reject on invalid drafts). Approve is pending-only.
11. **Retry creates a new draft** and closes the old one as rejected, so history is kept.
12. **R2/R5 ignore code `other`**, and raise one flag per code on the latest session in the window.
13. **Offline summaries are templated, not fixtures.** Summary inputs contain database ids, so
    hash-keyed fixtures would be brittle; `MockLLMClient` falls back to a deterministic template.
14. **Extra demo user `admin1`** (role admin) so the audit view and permission matrix can be shown.
15. **`factory_boy` is installed but unused**; tests use plain pytest fixtures.

## Not verified

- **No real LLM call has been made.** There was no API key in this environment, so
  `AnthropicLLMClient` is tested only against a fake SDK object, the prompts have never been run
  against a model, and `eval/report.md` is the mock sanity run (all 1.00 by construction). The
  quality targets in the AI brief are unmeasured. Run:
  `cd backend && LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... python ../eval/run_eval.py --client anthropic`
- **PostgreSQL is untested.** Everything ran on SQLite locally; the Postgres note-immutability
  trigger and the CI workflow have not been executed.
- **Python 3.14 locally** (spec and CI say 3.12). No `make` on this machine, so Makefile targets
  were run by hand, not through `make`.
- Time-based flags (late note, pending review) are only recomputed when something happens to the
  patient; see the `ponytail:` note in `rules/services.py`.

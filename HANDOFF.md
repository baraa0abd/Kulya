# HANDOFF

## Lead (M0 — contracts frozen)

### Models created (all migrated)

| App | Model | Notes |
|---|---|---|
| accounts | `User` | `AbstractUser` + `role` (nurse/doctor/patient/admin) + nullable `patient` FK. DB check: a patient-role user must have a patient. |
| clinical | `Patient` | `is_synthetic` defaults to true. |
| clinical | `Session` | Typo-guard validators (SBP 50–260, DBP 30–160, weight 20–250 kg, UF 0–8000 ml). Index `(patient, session_date)`. DB check `end_time > start_time`. |
| clinical | `Note` | Immutable: `save()` on an existing row and `delete()` raise `NoteImmutableError`; a DB trigger rejects any `UPDATE` (Postgres + SQLite). |
| clinical | `SessionFacts` | One row per session; `symptoms`, `access_findings`, `staff_actions` JSON lists. Write only on draft approval. |
| ai_engine | `ExtractionDraft` | Status pending/approved/rejected/invalid. |
| rules | `Flag` | Severity info/attention, `evidence` JSON, `rules_version`. |
| summaries | `Summary` | Audience clinician/patient, status draft/approved/rejected/invalid. |
| audit | `AuditLog` | Index `(object_type, object_id)`. |

### Endpoint stubs

Every path in `api_contract` is routed in `backend/kulya/urls.py` and appears in OpenAPI (`/api/schema/`,
Swagger at `/api/docs/`, table in `docs/api.md`). `POST /api/v1/auth/token` and `/auth/token/refresh` work
(simplejwt). **All other endpoints return 501** in the shared error format until their owner implements them.

To implement one: write the view in your app, then swap the `stub(...)` call in `kulya/urls.py` for your view.
Keep the path and the serializer names. Serializers already exist in each app's `serializers.py`.

### Utilities available

- `kulya.common.arabic.normalize_ar(text)` — use for every Arabic comparison.
- `kulya.common.errors.ApiError(code, message_ar, message_en, status_code, details)` — raise for a
  contract-shaped error. The DRF exception handler wraps all other errors into the same format.
- `ai_engine.client.LLMClient` (ABC, `complete_json(prompt_id, system, user, schema) -> dict`),
  `LLMOutputError`, `MockLLMClient`, `get_llm_client()`.
- `backend/gen_api_md.py` / `make docs` — regenerate `docs/api.md`.

### Left for the owning roles (stubs only, by design)

- backend: role permission classes and `role` JWT claim (B1), all views, audit service, DEMO_MODE guard (B8).
- ai: `MockLLMClient` only loads `tests/fixtures/llm/{prompt_id}/default.json`; per-input fixtures and
  `AnthropicLLMClient` are task A4. `get_llm_client()` raises for any provider other than `mock` until then.
  Add `anthropic` to `requirements.txt` in that task.
- rules_data: `seed_demo` command (`make seed`), `rules/config.yaml` (add `pyyaml`/`pydantic` then).
- devops: `docker-compose.yml` (`make demo`), README.

### Deviations from shared_context (with reasons)

1. **Six required vitals are nullable in the DB** (`pre/post_sbp`, `pre/post_dbp`, `pre/post_weight_kg`).
   `data_model` lists only `min_intra_sbp` and `uf_volume_ml` as nullable, but rule R3 and the SYN-003
   storyline need incomplete sessions to exist. The entry form may still require them.
2. **`SessionFacts` is one row per session** (OneToOne) holding three JSON lists; `data_model` did not fix the shape.
3. **`Summary.created_at` added** (not in `data_model`) for ordering.
4. **`POST /sessions/{id}/notes/` response** is `NoteCreated` = note fields + `draft_id` + `draft_status`.
5. **`PatientSerializer.attention_flag_count`** added because the frontend patient list (F2) needs it.
6. **Auth paths have no trailing slash** (`/auth/token`), exactly as written in `api_contract`; every other path has one.
7. **Local toolchain**: developed on Python 3.14 without GNU make; CI pins Python 3.12. Tests ran on SQLite
   locally; the Postgres trigger path runs in CI only (not yet executed anywhere).
8. **CI workflow has not been run** (no GitHub remote yet, `act` not installed).

### Test status

`backend`: 9 passed (L-T1 … L-T7 plus DB-trigger and error-format checks), ruff + black clean.
`frontend`: `flutter analyze` clean, default widget test passes (app is still the `flutter create` template).

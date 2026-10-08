# Test report

Run on 2026-10-08, Windows 11, Python 3.14, Node 24, PostgreSQL 16 + pgvector and Redis 7 in
Docker. All AI calls used the offline `MockProvider`. **No request was sent to the Claude API.**

## Results

| Suite | Command | Result |
|---|---|---|
| Backend (pytest, PostgreSQL) | `cd backend && python -m pytest` | **69 passed**, 3 consecutive full runs |
| Backend lint / format | `ruff check .`, `ruff format --check .` | clean |
| Migrations | `manage.py makemigrations --check` | no pending changes |
| Frontend unit + component (Vitest, RTL) | `npm test` | **9 passed** |
| Frontend lint | `npx eslint src` | clean |
| Frontend types | `npx tsc --noEmit` (strict) | clean |
| Frontend production build | `npx next build` | succeeded |
| End-to-end (Playwright, Chromium) | `npm run e2e` | **6 passed** (run twice, the second time after the last backend change) |
| Docker Compose | `docker compose up --build -d` | 5 services up; see below |

Backend breakdown: `test_security.py` 38, `test_ai.py` 23, `test_workflow.py` 8.

## What the tests cover

**Security** — unauthenticated rejection on every endpoint; role restrictions (vertical
escalation); assigned-patients-only access; cross-organization isolation; ended/inactive
assignments; IDOR on reads, writes and actions; immutability of signed records; patient view
limited to own released data; unauthorized summary release; per-report lab release; consent
grant, scope, revocation and expiry; private notifications; audit trail without clinical text;
errors that do not leak internals.

**AI** — reproducible deterministic checks; missing documentation, duration difference,
unresolved event, missing follow-up and conflicting-record checks; deterministic metrics with
nulls for missing inputs; de-identified context; retrieval limited to approved, in-date, same
organization passages; idempotent ingestion; schema-valid review draft with real citations;
rejection of extra fields, wrong session, invented record ids, invented protocol references and
out-of-role wording; provider timeout / error → `ai_unavailable` with rule findings kept and
session data unchanged; malformed output, ungrounded numbers and wrong duration rejected;
duplicate task delivery; unavailable protocol evidence; prompt injection in a nursing note;
summary versioning; provider request shape; missing API key fallback; broker unavailable.

**Workflow** — model and database constraints; session lifecycle with idempotent scheduling;
units, sources and plausible ranges; medication needs a valid order; amendments; event
resolution; versioned orders; rollback on a failed transaction; the full
nurse → AI → doctor → patient path through the API; the seed command.

**End-to-end (browser)** — doctor login and dashboard; nurse starts a session, records a vital,
is refused an out-of-range value, records an action, sees the completeness check, completes the
session; doctor sees the labelled AI draft with a cited passage, sends feedback, verifies and
releases the summary; nurse sees the feedback; patient sees the released summary; a patient is
redirected away from staff screens and refused by the API; a nurse from another team gets
"Not found"; signed-out access goes to login.

**Docker stack (manual check)** — backend healthy after migrate + seed; login through the
frontend proxy; nursing action accepted in 0.34 s; AI review produced by the Celery worker via
Redis and visible on the next poll (2 s).

## Defects found by testing and fixed

- Row locks combined with a nullable join failed on PostgreSQL (`FOR UPDATE` on an outer join).
- Idempotent replay could not store a response containing UUIDs.
- Number grounding first accepted any digits found anywhere in the context, including ids and
  timestamps and numbers written inside a nursing note. It now compares against real numeric
  values in structured fields only. This showed up as an intermittent test failure.
- 404 responses echoed the model name that was looked up.
- A circular import between the default permission class and DRF views.

## Not tested

- **The real Claude API.** `AnthropicProvider` is exercised only against a fake SDK object. The
  prompts have never been run against a model, so AI output quality, validation pass rate and
  latency with a real model are unknown.
- Retrieval quality. The embedding is a lexical hash; only basic relevance was checked.
- Rate limiting (configured, disabled in tests).
- GitHub Actions workflow and the gitleaks job (never executed).
- Python 3.12 (tests ran on 3.14; the Docker image uses 3.12 and started correctly).
- Concurrency and load; multiple backend instances.
- Backup and restore; HTTPS proxy settings.
- Mobile layouts were not checked in a browser (the layout uses responsive grids).
- Accessibility was not audited (forms have labels; charts have text alternatives and tables).
- mypy was not run.

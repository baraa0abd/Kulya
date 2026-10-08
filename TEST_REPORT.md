# Test report

Run on 2026-10-08, Windows 11, Python 3.14, Node 24, PostgreSQL 16 + pgvector and Redis 7 in
Docker. All AI calls used the offline `MockProvider`. **No request was sent to the Claude API.**

## Results

| Suite | Command | Result |
|---|---|---|
| Backend (pytest, PostgreSQL) | `cd backend && python -m pytest` | **98 passed** (2 consecutive full runs after the nutrition module) |
| Backend lint / format | `ruff check .`, `ruff format --check .` | clean |
| Migrations | `manage.py makemigrations --check` | no pending changes |
| Frontend unit + component (Vitest, RTL) | `npm test` | **11 passed** |
| Frontend lint | `npx eslint src` | clean |
| Frontend types | `npx tsc --noEmit` (strict) | clean |
| Frontend production build | `npx next build` | succeeded |
| End-to-end (Playwright, Chromium) | `npm run e2e` | `nutrition.spec.ts` **7 passed**. `workflow.spec.ts` **7 passed** (re-run after the nutrition work). Run the two files separately: together they exceed the 10/min sign-in limit |
| Docker Compose | `docker compose up --build -d` | 5 services up; see below |

Backend breakdown: `test_security.py` 38, `test_ai.py` 23, `test_workflow.py` 8, `test_nutrition.py` 29.

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

**Arabic interface** — the app loads Arabic and right-to-left, sign-in works in Arabic, the nurse
dashboard headings are Arabic, and the toggle switches to English left-to-right (1 browser test,
1 unit test). The other browser tests run with the interface switched to English.

**Interface redesign** — after the design system was applied, all frontend checks were re-run
(10 unit tests, 7 browser tests, lint, type-check, build) with no change to the backend. Screens
reviewed from full-size screenshots: nurse dashboard (Arabic), doctor dashboard and session review
(English), patient dashboard (Arabic). Not visually reviewed: the nurse session screen, the doctor
patient page, the family view, the sign-in page after restyling, and any phone or tablet width.

## Defects found by testing and fixed

- Row locks combined with a nullable join failed on PostgreSQL (`FOR UPDATE` on an outer join).
- Idempotent replay could not store a response containing UUIDs.
- Number grounding first accepted any digits found anywhere in the context, including ids and
  timestamps and numbers written inside a nursing note. It now compares against real numeric
  values in structured fields only. This showed up as an intermittent test failure.
- 404 responses echoed the model name that was looked up.
- A circular import between the default permission class and DRF views.
- A hydration mismatch when the saved language was English (the pages sat inside a Suspense
  boundary and hydrated after the language switch).
- In Arabic, values with units rendered reversed ("min 240") and charts were mirrored.

## Nutrition module (2026-10-08)

`test_nutrition.py` (29): nutrient arithmetic and null handling; missing diary days; recipe
classification; Arabic and plural food matching; server-side estimates; correction and withdrawal;
recognition proposes without saving; provider failure and smuggled nutrient fields fall back to
manual entry; care-team, tenant and patient isolation; family consent scopes, revocation and
expiry; plan approval rights and versioning; general versus personalized suggestions and their
visibility; rejection of causal claims, creatinine statements, medication advice, invented numbers
and unknown citations; food-and-lab review idempotency; report draft, release and what a patient
sees inside it; nurse referral notifications; USDA client against a fake response.

`e2e/nutrition.spec.ts` (7, Chromium, mock provider): patient records a meal after confirming each
line; patient sees only approved ideas and no draft; dietitian approves an idea and releases the
report; patient then sees it; nurse cannot approve; family access follows consent (granted and
expired); Arabic RTL. Screenshots of the Arabic overview, the add-meal screen and the clinician
page were looked at by the developer.

Not tested in the nutrition module: any real model (text or photo); real speech input; the real
USDA API; printing to PDF; mobile layouts; the lab-review and report screens in Arabic; behaviour
with a Celery worker (tests and the local run execute tasks inline; the endpoints return 202 when
a worker is used and the screen then needs a reload).

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
- The Arabic wording was written by the developer and not reviewed by a clinician or a native
  medical translator. Only the sign-in page and nurse dashboard were checked in Arabic in a browser;
  the other screens were not visually reviewed in RTL. Server-generated text (finding descriptions,
  AI drafts, API error messages) is still English.
- Mobile layouts were not checked in a browser (the layout uses responsive grids).
- Accessibility was not audited (forms have labels; charts have text alternatives and tables).
- mypy was not run.

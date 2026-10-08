# Security

Scope: a hackathon demo on synthetic data. This describes what is implemented and tested, and what
is not. It is not a claim of compliance with any health-data regulation.

## Implemented and covered by automated tests

- **Authentication**: JWT (15-minute access, 12-hour refresh); service accounts cannot log in.
  Rate limits (login, AI requests, per user, anonymous) are configured but not covered by a test.
- **Default deny**: unauthenticated requests get 401 on every endpoint; a view with no declared
  roles is closed.
- **Role checks**: nurses cannot verify or release AI output, write feedback, or create orders;
  doctors cannot write nursing documentation; admin and auditor roles get no clinical data.
- **Patient-level access**: staff reach only patients with an active care assignment in their own
  organization. Ended or inactive assignments remove access.
- **Tenant isolation**: another organization's staff get nothing, even with a stray assignment.
- **IDOR**: ids outside the caller's scope return 404 on reads, writes and custom actions.
- **Consent**: family access requires an unexpired, unrevoked grant with the matching scope.
- **Release control**: patients and caregivers see AI text only when verified and released; this
  is also a database constraint. Lab reports are released per report by a doctor.
- **Record integrity**: signed records cannot be updated or deleted; corrections are amendments.
- **Audit**: writes and sensitive reads are logged with actor, action, object and patient id.
  Audit metadata holds ids and states, never clinical text. Audit rows are append-only.
- **AI safety**: no tools are exposed to the model; authorization happens outside it; record text
  is passed as data; output is schema-validated; cited records and protocol passages must exist;
  numbers must be real values from the record; diagnosing/prescribing/staff-grading/machine-control
  wording is rejected. A prompt-injection note is tested: an output that obeys it is rejected.
- **Failure behaviour**: provider or validation failure yields `ai_unavailable`, never a fake
  success; original records are untouched; a missing worker or broker does not block writes.
- **Errors and logs**: one error shape, no stack traces, 404 messages do not name what was looked
  up; logs are JSON with ids and event names only.
- **Configuration**: all secrets from environment; `.env` is git-ignored; outside DEBUG/DEMO the
  app refuses to start with the default secret key; secure-cookie, HSTS and SSL-redirect settings
  are available by environment variable. Database and Redis ports bind to loopback only.

### Nutrition module

- Every `/api/nutrition/` endpoint is behind `RolePolicy` and `patients_for`; out-of-scope ids
  answer 404 (tested for unassigned staff, another organization, another patient, no consent,
  wrong consent scope, revoked and expired consent).
- Reading the diary and recording meals are separate family consent scopes.
- Nurses and patients cannot approve plans, review AI drafts or release reports (403, tested).
- Patients and caregivers see only approved personalized suggestions, approved food-and-lab
  reviews and released reports; inside a released report, laboratory results appear only if a
  doctor released that laboratory report (and, for a caregiver, the `labs` scope is granted).
- Meal photos are not stored. The USDA key is sent in a header, never in a URL.
- Text in a meal description or photo is treated as data; the recognition schema has no field
  through which a model could set a nutrient value (tested).

## Known gaps (not done)

- Tokens are kept in `sessionStorage`, readable by any script on the page. HttpOnly cookie
  sessions with CSRF protection would be stronger.
- No multi-factor authentication, account lockout, password reset, or token revocation list.
- No encryption at rest beyond what the database host provides; no field-level encryption.
- Rate limits use Django's per-process cache, so they are not shared across workers.
- The forbidden-wording check is a substring list. It will miss novel phrasing; the reviewing
  doctor is the real control.
- Dates and clock times in AI prose are not checked against the record.
- `npm audit --omit=dev` reports 7 high-severity advisories, all from `braces` pulled in by the
  `shadcn` CLI package (build-time tooling, not served to browsers). Not fixed. No Python
  dependency audit was run.
- No penetration test, no threat model review, no privacy impact assessment.
- The gitleaks CI job has not been run.
- Nutrition: voice entry uses the browser's speech recognition, which in Chromium sends audio to
  the browser vendor. With `LLM_PROVIDER=anthropic`, meal photos and descriptions are sent to the
  model provider. Neither has had a privacy review. The causal-wording filter is a keyword list
  and can be evaded by paraphrase; clinician review is the real control.

## Before any real-patient use

Privacy, security, regulatory and clinical validation are all required and none has been done:
clinician-approved protocols in place of the synthetic policy, clinical review of every rule and
prompt, a data-protection assessment, hardened hosting, backups with tested restore, monitoring,
incident response, and a real-model evaluation of AI output quality.

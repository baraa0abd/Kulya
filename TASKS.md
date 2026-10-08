# Tasks

Statuses: TODO, IN_PROGRESS, BLOCKED, TESTING, DONE. A task is DONE only with executed evidence
(see `TEST_REPORT.md`). Priorities: P0 must work for the demo, P1 expected, P2 nice to have.

| ID | Description | Pri | Depends | Status | Tests executed / evidence | Known limitations |
|---|---|---|---|---|---|---|
| T01 | Repository inspection, architecture, contracts, safety boundaries | P0 | — | DONE | `ARCHITECTURE.md`, `SECURITY.md` | Replaced the earlier Kulya (Flutter) app on branch `kulya` |
| T02 | Django + PostgreSQL + pgvector + Redis + Celery configuration | P0 | T01 | DONE | compose stack started; migrations apply | Tested on Python 3.14 locally, 3.12 in the image |
| T03 | Data model: 23 entities, UUID keys, units, immutability, versioning | P0 | T02 | DONE | `test_model_constraints`, migrations check | — |
| T04 | Authentication, RBAC, object-level authorization, tenant isolation | P0 | T03 | DONE | `test_security.py` (38) | JWT in sessionStorage; no MFA, lockout or password reset |
| T05 | Care assignments and consent grants | P0 | T04 | DONE | assignment, consent, expiry tests | Only an org admin changes care teams, API only (no screen) |
| T06 | Clinical APIs: sessions, vitals, actions, notes, readings, events, labs, orders | P0 | T04 | DONE | `test_workflow.py`, E2E nurse flow | No session cancel endpoint; no incident-specific form |
| T07 | Audit log | P0 | T04 | DONE | audit tests; `/api/audit/` | No audit screen in the frontend |
| T08 | Synthetic seed data (2 orgs, 16 accounts, 4 patients, 24 sessions, labs, policy) | P0 | T06 | DONE | `test_seed_demo...`; seeded 3 times | — |
| T09 | Deterministic documentation checks (7) | P0 | T06 | DONE | rules tests; seeded gap cases detected | Follow-up rule is a synthetic workflow policy, not clinical |
| T10 | RAG: ingestion, chunking, embeddings, pgvector retrieval, citation checks | P0 | T02 | DONE | retrieval and approval/expiry/org tests | Lexical hashing embedding, not semantic; one synthetic policy; text/markdown ingestion only (no PDF extraction) |
| T11 | LLM provider abstraction, versioned prompts, mock provider | P0 | — | DONE | provider tests | — |
| T12 | AI documentation review: pipeline, validation, fallback, idempotency | P0 | T09–T11 | DONE | `test_ai.py`, E2E doctor flow, worker check | Real-model behaviour untested |
| T13 | AI session summaries: metrics, validation, versions, verify, release | P0 | T11 | DONE | summary tests, E2E release flow | Real-model behaviour untested; dates/times in prose unchecked |
| T14 | Doctor feedback, review tasks, notifications | P0 | T12 | DONE | workflow test, E2E feedback | Notifications are in-app only (no email/SMS/push) |
| T15 | Doctor dashboard (reviews, patients, activity, labs, AI review, summary, feedback) | P0 | T06, T12–T14 | DONE | E2E tests 1 and 3; build | Lists show the first 50 rows; no search |
| T16 | Nurse dashboard (schedule, session forms, timeline, completeness, feedback inbox) | P0 | T06 | DONE | E2E tests 2 and 4 | No amendment or medication-order form in the UI (API supports both) |
| T17 | Patient and family dashboard (summaries, sessions, labs, sharing, home measurements) | P0 | T05, T13 | DONE | E2E test 5; consent API tests | Family view not covered by a browser test; no symptom journal |
| T18 | Prompt-injection defence | P0 | T12 | DONE | injection test | Tested with a scripted provider, not a real model |
| T19 | Failure handling (provider, malformed output, worker down, duplicates, transactions) | P0 | T12 | DONE | failure tests | — |
| T20 | Docker Compose with health checks; frontend and backend images | P1 | T15–T17 | DONE | stack started and exercised | No TLS proxy included |
| T21 | CI workflow (lint, tests, build, compose build, secret scan) | P1 | T20 | TESTING | file written | **Never executed** (no remote) |
| T22 | Documentation: README, architecture, security, deployment, test report, OpenAPI | P1 | all | DONE | files present; `docs/openapi.yaml` generated | — |
| T30 | Arabic right-to-left interface with English toggle | P1 | T15–T17 | DONE | Arabic E2E test, i18n unit test, build | Server-generated text stays English; wording not reviewed by a clinician; only two screens checked visually in RTL |
| T23 | Real Claude API evaluation of both AI features | P0 | T12, T13 | BLOCKED | — | Needs `ANTHROPIC_API_KEY`; none available in this environment |
| T24 | Semantic embedding model for retrieval | P1 | T10 | BLOCKED | — | Needs an embedding provider and key |
| T25 | Clinician-approved protocols and clinical review of rules and prompts | P0 for real use | — | BLOCKED | — | Needs clinicians; synthetic policy used meanwhile |
| T26 | Patient symptom journal | P2 | T17 | TODO | — | Not built; no entity for it in the required model list |
| T27 | Org-admin and audit screens; care-team management UI | P2 | T05, T07 | TODO | — | API only |
| T28 | Rate-limit test, mypy, Python dependency audit, accessibility and mobile review | P2 | — | TODO | — | Not done |
| T29 | HttpOnly cookie sessions, MFA, password reset | P1 for real use | T04 | TODO | — | Not done |

## Requirement status against the definition of done

| Requirement | Status |
|---|---|
| Three dashboards on real backend endpoints | Works (browser-tested for doctor, nurse, patient) |
| Users only access authorized patient records | Works (38 security tests) |
| Nurses can document dialysis sessions | Works |
| Nursing actions are recorded and auditable | Works |
| Assigned doctors can review nursing activity | Works |
| AI documentation review generates validated drafts | Works with the mock provider; real model untested |
| AI session summaries generate validated drafts | Works with the mock provider; real model untested |
| Doctors can add feedback; nurses can view it | Works |
| Patients can view clinician-released summaries | Works |
| Workflow demonstrable end to end on synthetic data | Works (API test and browser E2E) |
| Migrations succeed; frontend production build succeeds | Yes |
| No known critical authorization vulnerability | None known; no external security review |

## Readiness

**Functional demo** (level 2 of 4). Not an engineering release candidate: CI has never run, the AI
has never been exercised with a real model, and several production controls are missing. Not
clinically validated, and software tests alone could never make it so.

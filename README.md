# Dialysis Copilot

Dialysis session documentation, AI-assisted documentation review, and AI session summaries for
nurses, doctors, patients and family caregivers.

**Status: functional hackathon demo on synthetic data. Not a medical device. Not validated for
real patients.** See `TEST_REPORT.md` for what was actually tested and `SECURITY.md` /
`DEPLOYMENT.md` for what real use would still require.

## Quick start (Docker)

```bash
cp .env.example .env        # then set DEMO_PASSWORD (and DJANGO_SECRET_KEY)
docker compose up --build
```

Open http://localhost:3000 and sign in with a demo account and your `DEMO_PASSWORD`.

| Account | Role | Sees |
|---|---|---|
| `doctor1` | doctor | SYN-001, SYN-002 |
| `doctor2` | doctor | SYN-003 |
| `nurse1`–`nurse3` | nurse | SYN-001, SYN-002 |
| `nurse4`–`nurse6` | nurse | SYN-003 |
| `patient1`–`patient3` | patient | own released records |
| `family1` | family caregiver | SYN-001 summaries and appointments (consent) |
| `family2` | family caregiver | nothing (consent expired) |
| `auditor1`, `orgadmin1` | audit / admin | no clinical data |

## Local development

```bash
docker compose up -d db redis                       # Postgres + pgvector on :5433, Redis on :6380
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # bin/ on Linux/macOS
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_demo            # needs DEMO_PASSWORD in ../.env
.venv/Scripts/python manage.py runserver 8000
cd ../frontend && npm ci --legacy-peer-deps && npm run dev      # http://localhost:3000
```

AI jobs run inline by default (`CELERY_TASK_ALWAYS_EAGER=true`). With Docker Compose they run in
a real Celery worker. The default `LLM_PROVIDER=mock` needs no key; set `LLM_PROVIDER=anthropic`
and `ANTHROPIC_API_KEY` to use Claude.

## Tests

```bash
cd backend  && .venv/Scripts/python -m pytest          # 69 tests, needs the db container
cd frontend && npm test                                # 9 unit/component tests
cd frontend && npx playwright install chromium && npm run e2e   # 6 E2E tests, needs the stack running
```

The E2E run changes today's session for SYN-001. Reset the demo data afterwards:
`python manage.py flush --noinput && python manage.py seed_demo`.

## Where things are

- `backend/` Django + DRF API (`core`, `clinical`, `ai`, `workflow`), Celery tasks, tests
- `frontend/` Next.js + TypeScript + Tailwind + shadcn/ui dashboards
- `docs/openapi.yaml` generated API schema (live at `/api/docs/` on the backend)
- `ARCHITECTURE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `TASKS.md`, `TEST_REPORT.md`

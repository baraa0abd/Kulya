# Kulya

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

The interface is Arabic and right-to-left by default; the **English** button in the header (and on
the sign-in page) switches language. Record content and AI drafts are shown as stored.

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
cd backend  && .venv/Scripts/python -m pytest          # 98 tests, needs the db container
cd frontend && npm test                                # 11 unit/component tests
cd frontend && npx playwright install chromium && npm run e2e   # 14 E2E tests, needs the stack running
```

The E2E run changes today's session, the diary and a report for SYN-001. Sign-in is limited to 10 per minute,
so run the two spec files separately (`npx playwright test e2e/nutrition.spec.ts`) or raise `THROTTLE_LOGIN`. Reset the demo data afterwards:
`python manage.py flush --noinput && python manage.py seed_demo`.

## Where things are

- `backend/` Django + DRF API (`core`, `clinical`, `ai`, `workflow`, `nutrition`), Celery tasks, tests
- `frontend/` Next.js + TypeScript + Tailwind + shadcn/ui dashboards
- `docs/openapi.yaml` generated API schema (live at `/api/docs/` on the backend)
- `ARCHITECTURE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `TASKS.md`, `TEST_REPORT.md`

## Renal nutrition

Patients (or a caregiver they allow) keep a food diary by typing, speaking or photographing a
meal; the assistant proposes foods and the person confirms each line. Nutrient estimates are
calculated by the server from the food catalogue. A doctor or dietitian approves the nutrition
plan, reviews AI drafts and releases reports. Demo account for the new role: `dietitian1`.

- The bundled food catalogue (`backend/nutrition/data/catalog.json`) is **approximate and
  unverified**. `python manage.py load_food_catalog` loads it; `seed_demo` does this for you.
- Optional: set `USDA_API_KEY` to let a doctor or dietitian import foods from USDA FoodData
  Central (`/api/nutrition/foods/?q=...&source=usda`).
- This module is a demonstration. It is not medically validated and must not be used with real
  patients without clinical assessment, privacy review and any required regulatory clearance.

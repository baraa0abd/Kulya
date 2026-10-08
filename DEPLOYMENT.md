# Deployment

This describes how to run the demo stack. It is not a production runbook: the system has not been
validated for real patients (see `SECURITY.md`).

## Docker Compose

```bash
cp .env.example .env    # set DEMO_PASSWORD, DJANGO_SECRET_KEY, POSTGRES_PASSWORD
docker compose up --build -d
docker compose ps       # db, redis, backend should report healthy
```

| Service | Image / build | Port (loopback) | Health check |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5433 | `pg_isready` |
| `redis` | `redis:7-alpine` | 6380 | `redis-cli ping` |
| `backend` | `./backend` (gunicorn, non-root) | 8000 | `GET /api/health/` |
| `worker` | `./backend` (Celery) | — | `celery inspect ping` |
| `frontend` | `./frontend` (Next.js standalone, non-root) | 3000 | — |

On start the backend runs `migrate` then `seed_demo` (idempotent). The worker starts after the
backend is healthy. All ports bind to 127.0.0.1; put a TLS-terminating reverse proxy in front for
anything beyond a local demo.

## Configuration

Everything is an environment variable; see `.env.example`. For a non-demo deployment set at least:

- `DJANGO_DEBUG=false`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
- `SECURE_SSL_REDIRECT=true`, `SECURE_HSTS_SECONDS=31536000` (behind an HTTPS proxy)
- `DJANGO_CSRF_TRUSTED_ORIGINS` if the admin is used through the proxy
- `CELERY_TASK_ALWAYS_EAGER=false` with a running worker
- `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` from a secret manager, never in the image
- Do **not** run `seed_demo`

The frontend's API target (`BACKEND_URL`) is fixed at image build time (`docker compose` passes it
as a build argument).

## Database

- Migrations: `python manage.py migrate` on every release, before the new code serves traffic.
  The first `ai` migration enables the `vector` extension, so the database role needs permission
  to create extensions (or enable `vector` beforehand).
- Backup: `docker compose exec db pg_dump -U kulya -Fc kulya > backup.dump`
- Restore: `docker compose exec -T db pg_restore -U kulya -d kulya --clean < backup.dump`
- These commands are the standard PostgreSQL procedure; a restore was **not** rehearsed here.

## Operations

- Logs are JSON lines on stdout (ids and event names only). Ship them to your log system.
- No error-monitoring service is wired in.
- `GET /api/health/` checks the database connection only.
- If the worker or Redis is down, clinical writes still succeed; AI reviews and summaries are
  simply not produced until a doctor requests them again.

## Verified in this repository

- `docker compose up --build`: all five services started; backend healthy after migrate + seed;
  login worked through the frontend proxy; a nursing action returned in 0.34 s and its AI review
  was produced by the Celery worker within 2 s.
- Not verified: the GitHub Actions workflow (never run), HTTPS/proxy settings, backup and restore,
  multi-instance operation, and anything with the real Claude API.

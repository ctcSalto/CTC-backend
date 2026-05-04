# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Backend for CTC (Centro de Tecnologías de la Comunicación) in Salto, Uruguay. FastAPI application managing educational careers, users, testimonies, news, and integrations with Moodle LMS, MercadoPago payments, Google Workspace (via n8n), and Google Analytics 4. An embedded SvelteKit admin panel is served at `/admin`.

**Language:** Spanish — code comments, commit messages, and documentation are in Spanish.

## Commands

```bash
# Run dev server (port 8000)
python main.py

# Or directly with uvicorn
uvicorn main:app --host=0.0.0.0 --port=8000

# Windows quick start (creates venv, installs deps, runs)
start.bat

# Install dependencies
pip install -r requirements.txt

# Database migrations
alembic revision --autogenerate -m "descripción del cambio"
alembic upgrade head

# Run tests
pytest

# Frontend admin panel (SvelteKit)
cd frontend && npm install && npm run build
```

## Architecture

### Layered Structure

```
main.py                    → App entry point, lifespan (startup/shutdown), router registration
routes/                    → API endpoint handlers (controllers)
database/services/         → Business logic layer (services)
database/models/           → SQLModel entities (User, Career, Testimony, News)
external_services/         → Third-party API wrappers (Moodle, MercadoPago, Google)
utils/                     → Scheduler (APScheduler), logger (IceCream), background jobs
exceptions/                → Custom AppException hierarchy
```

### Service Singleton

`database/database.py` defines a `Services` class instantiated once via `get_services()`. All services (UserService, CareerService, CacheService, RedisService, SupabaseService, etc.) are accessed through this singleton. Database sessions use `get_session()` as a FastAPI dependency or `get_db_session()` context manager outside of request handlers.

### Authentication

JWT-based with Redis token blacklist for logout. Auth dependencies in `database/services/auth/dependencies.py`. Roles: `ADMIN`, `STUDENT`. Password hashing with bcrypt. Token expiry configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480).

### Redis Cache

Cache-aside pattern with two services:
- `CacheService` — careers data with prefix `career:*` / `careers:*` (TTL 1h, warmup 2h)
- `AnalyticsCacheService` — Google Analytics data

All write operations (create/update/delete) invalidate the entire career cache. Redis is non-critical; app falls back to DB on failure.

### Advanced Filter System

`database/services/filter/filters.py` — reusable `QueryBuilder` supporting dynamic conditions (AND/OR groups), operators (eq, ne, contains, icontains, in, is_null, etc.), eager loading, field selection, and pagination. Used across entities via `/filters` and `/public/filters` endpoints.

### External Integrations

- **Moodle** (`external_services/moodle_api/`) — user, course, category, enrolment management via token-based API. Weekly Playwright script updates profile photos.
- **MercadoPago** (`external_services/mercadopago_api/`) — payment preferences, subscriptions, webhook handling.
- **Supabase** (`database/services/supabase/image_service.py`) — image storage with automatic WebP conversion (85% quality), EXIF rotation fix, UUID filenames.
- **Google Workspace** (`external_services/google/google_service.py`) — account management via n8n webhooks (not direct API).
- **Google Analytics 4** (`external_services/google/analytics/`) — GA4 data via service account, pre-fetched every 4 hours.

### Scheduler

`utils/scheduler.py` — APScheduler cron jobs, **only runs when `ENVIRONMENT=production`**:
- Sundays 2:00 AM (America/Montevideo): Moodle profile photo update
- Every 4 hours: Analytics data pre-fetch

### Frontend Admin Panel

SvelteKit app in `frontend/`, built to `frontend/build/`, mounted at `/admin` via FastAPI static files. Uses Svelte 5, TailwindCSS 4, adapter-static.

## Key Conventions

- **Timezone:** All dates use `America/Montevideo` (Uruguay)
- **Audit trail:** All entities track `creator`, `modifier`, `creationDate`, `modificationDate`
- **Publication workflow:** Entities have `published` (bool) and `publicationDate` fields; public endpoints auto-filter to published=true
- **Career types:** `CAREER`, `COURSE`, `WORKSHOP`, `DIPLOMA`
- **Career areas:** `ADMINISTRATION`, `COMMUNICATION`, `CULTURE`, `GENERAL`, `IT`
- **ORM:** SQLModel (SQLAlchemy + Pydantic). Separate Create/Update/Read schemas per model
- **Deployment:** Heroku/EasyPanel via `Procfile`
- **API docs:** Scalar UI at `/docs-scalar`, standard Swagger at `/docs`
- **Environment:** `.env` file for dev (see `.env.example`), system env vars for production

## Environment Variables

Required — see `.env.example` for full list. Key groups: `DATABASE_URL`, `SECRET_KEY`, `REDIS_*`, `SUPABASE_*`, `MOODLE_*`, `MERCADOPAGO_*`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`, `GA4_PROPERTY_ID`, `N8N_*`, `ENVIRONMENT`.

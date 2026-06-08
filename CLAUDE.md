# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Backend for CTC (Centro de Tecnologías de la Comunicación) in Salto, Uruguay. FastAPI application with two major subsystems:

1. **V1** — public website backend: careers, users, testimonies, news, plus integrations with Moodle LMS, MercadoPago payments, Google Workspace (via n8n), and Google Analytics 4.
2. **V2 (Portal Académico)** — academic management system under `v2/`: programs, subjects, enrollments, grading, exams, prerequisites, documents. Uses Google OAuth for authentication (restricted to `@ctcsalto.edu.uy`).

An embedded SvelteKit admin panel is served at `/admin`.

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

# Run tests (v2 tests with conftest fixtures)
pytest
pytest v2/tests/                    # v2 tests only
pytest v2/tests/test_calificaciones.py  # single test file
pytest v2/tests/test_calificaciones.py::test_nombre  # single test

# Root-level test files (test_fase*.py) require a running server on localhost:8000

# Frontend admin panel (SvelteKit)
cd frontend && npm install && npm run build
```

## Architecture

### Layered Structure

```
main.py                    → App entry point, lifespan (startup/shutdown), router registration
routes/                    → V1 API endpoint handlers
database/services/         → V1 business logic layer
database/models/           → V1 SQLModel entities (User, Career, Testimony, News)
v2/                        → Portal Académico (complete parallel subsystem)
  v2/routes/               → V2 API routes (all prefixed /v2)
  v2/services/             → V2 business logic (19 services)
  v2/models/               → V2 SQLModel entities (23+ models)
  v2/auth/                 → Google OAuth + JWT (separate from v1 auth)
  v2/tests/                → pytest suite with conftest.py fixtures
external_services/         → Third-party API wrappers (Moodle, MercadoPago, Google)
utils/                     → Scheduler (APScheduler), logger (IceCream), background jobs
exceptions/                → Custom AppException hierarchy (message + status_code)
frontend/                  → SvelteKit admin panel (Svelte 5, TailwindCSS 4, adapter-static)
```

### Service Singletons

Both v1 and v2 use the same singleton pattern:

- **V1:** `database/database.py` → `Services` class via `get_services()`. Contains UserService, CareerService, CacheService, RedisService, SupabaseService, etc.
- **V2:** `v2/services/__init__.py` → `V2Services` class via `get_v2_services()`. Contains 19 services (UsuarioService, ProgramaService, MateriaService, InscripcionService, etc.).

### Database Sessions

Two patterns depending on context:
- **FastAPI routes:** `get_session()` dependency (auto-commit/rollback)
- **Outside requests** (scheduler, tests, scripts): `get_db_session()` context manager

### Authentication

**V1:** JWT-based with Redis token blacklist for logout. Auth dependencies in `database/services/auth/dependencies.py`. Roles: `ADMIN`, `STUDENT`. Password hashing with bcrypt.

**V2:** Google OAuth 2.0 (restricted to `@ctcsalto.edu.uy` domain) + JWT. Auth in `v2/auth/`. Roles: `ESTUDIANTE`, `DOCENTE`, `ADMINISTRATIVO`. Dedicated portal routes per role (`/v2/portal/estudiante/*`, `/v2/portal/docente/*`).

### Redis Cache

Cache-aside pattern with two services:
- `CacheService` — careers data with prefix `career:*` / `careers:*` (TTL 1h, warmup 2h)
- `AnalyticsCacheService` — Google Analytics data

All write operations (create/update/delete) invalidate the entire career cache. Redis is non-critical; app falls back to DB on failure.

### Advanced Filter System

`database/services/filter/filters.py` — reusable `QueryBuilder` supporting dynamic conditions (AND/OR groups), operators (eq, ne, contains, icontains, in, is_null, etc.), eager loading, field selection, and pagination. Used across v1 entities via `/filters` and `/public/filters` endpoints and in v2 admin routes.

### V2 Grading & Snapshot Pattern

`v2/services/grading_engine.py` is a pure function (no DB access) that calculates student states (CURSANDO, EXONERADO, A_EXAMEN, APROBADO, REPROBADO). `InscripcionMateria` stores frozen copies of grading policies and evaluation instances at enrollment time, ensuring grade calculations remain consistent even if policies change later.

### V2 Prerequisites

`v2/models/previatura.py` — prerequisite relationships between subjects with cycle detection in the service layer. Enrollment validation checks prerequisite completion.

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

SvelteKit app in `frontend/`, built to `frontend/build/`, mounted at `/admin` via FastAPI static files (SPA mode with fallback to `index.html`). Uses Svelte 5, TailwindCSS 4, adapter-static.

## Key Conventions

- **Timezone:** All dates use `America/Montevideo` (Uruguay)
- **Audit trail:** All entities track `creator`, `modifier`, `creationDate`, `modificationDate`
- **Publication workflow:** V1 entities have `published` (bool) and `publicationDate` fields; public endpoints auto-filter to published=true
- **Soft deletes (V2):** Enrollment abandonment/withdrawal changes `estado` with `fecha_baja` and `motivo_cierre`
- **ORM:** SQLModel (SQLAlchemy + Pydantic). Separate Create/Update/Read schemas per model
- **V2 enums:** 14 string enums in `v2/models/enums.py` (RolUsuario, EstadoInscripcionMateria, TipoPrograma, etc.)
- **Deployment:** Heroku/EasyPanel via `Procfile`
- **API docs:** Scalar UI at `/docs-scalar`, standard Swagger at `/docs`
- **Environment:** `.env` file for dev (see `.env.example`), system env vars for production

## Testing

**V2 tests** (`v2/tests/`): pytest with SQLite in-memory fixtures in `conftest.py`. Key fixtures: `fixture_engine`, `fixture_session`, `fixture_programa`, `fixture_usuario_estudiante/docente/admin`, `fixture_inscripcion_cursando`. Auth helpers: `make_token(usuario)`, `make_headers(usuario)`.

**Integration tests** (root `test_fase*.py`): require a running server on `localhost:8000`. Use `setup_admin_user()` to create test users directly via `get_db_session()`.

## Environment Variables

Required — see `.env.example` for full list. Key groups: `DATABASE_URL`, `SECRET_KEY`, `REDIS_*`, `SUPABASE_*`, `MOODLE_*`, `MERCADOPAGO_*`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`, `GA4_PROPERTY_ID`, `N8N_*`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GOOGLE_ALLOWED_DOMAIN`, `ENVIRONMENT`.

# Epic 3: Infra & Deploy

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-3 |
| **Title** | Infrastructure, Deployment & Production Configuration |
| **Status** | Draft |
| **Repositories** | instagram-campaign-api + instagram-campaign-web |
| **Stories** | 3 |
| **PRD Reference** | `docs/prd/PRD-instagram-campaign.md` |
| **Depends On** | EPIC-1 (API), EPIC-2 (Frontend) |

---

## Goal

Containerize, deploy, and configure production infrastructure for both the API (Railway) and the frontend (Vercel), ensuring the system operates reliably with proper environment configuration, CORS lockdown, scheduler activation, health monitoring, and structured logging. By the end of this epic, the complete application is live and accessible.

---

## Scope

### In Scope
- Docker image optimization for the FastAPI API
- Railway service creation and configuration
- Vercel project setup for the Next.js frontend
- Production environment variables for both services
- CORS lockdown (replace wildcard with frontend domain)
- Scheduler activation in production environment
- Health check monitoring configuration
- Structured logging verification in production
- SSL/HTTPS (provided by Railway and Vercel by default)

### Out of Scope
- Custom domain setup (use Railway and Vercel default domains for MVP)
- CDN configuration beyond Vercel defaults
- Alerting/notification systems (email, Slack)
- CI/CD pipeline (GitHub Actions) -- manual deploy for MVP
- Auto-scaling configuration
- Database backups (Supabase handles this)

---

## Dependencies

- Epic 1 fully implemented (API ready for deployment)
- Epic 2 fully implemented (Frontend ready for deployment)
- Supabase project configured with production credentials
- Apify account with production API token
- Railway account
- Vercel account
- LLM API key for production use

---

## Stories

---

### Story 3.1: API Dockerization & Railway Deploy

**As a** devops engineer,
**I want** the FastAPI API containerized with an optimized Docker image and deployed to Railway,
**so that** the backend is accessible over the internet for the frontend to consume.

**PRD References**: NFR-007, CON-003, CON-006

#### Acceptance Criteria

1. The existing `Dockerfile` in `instagram-campaign-api` is optimized for production:
   - Multi-stage build (builder stage for dependencies, runtime stage for execution).
   - Final image based on `python:3.11-slim` (not full Python image).
   - `requirements.txt` dependencies installed in builder stage and copied to runtime.
   - Non-root user for the application process.
   - Health check instruction (`HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1`).
   - Image size target: < 200MB.
2. A `railway.toml` or `railway.json` configuration file defines the service settings:
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
   - Health check path: `/health`.
3. The following environment variables are documented in `.env.example` and must be set in Railway:
   - `SUPABASE_URL`, `SUPABASE_KEY`
   - `APIFY_TOKEN`
   - `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`
   - `SCRAPING_INTERVAL_HOURS`
   - `ALLOWED_ORIGINS` (for CORS)
   - `LOG_LEVEL`
4. The API is deployed to Railway and responds to `GET /health` returning `{"status": "ok"}` with database connectivity confirmed.
5. FastAPI auto-docs are accessible at `{railway-url}/docs`.
6. Docker image builds successfully locally with `docker build -t instagram-campaign-api .` and runs with `docker run -p 8000:8000 instagram-campaign-api`.

#### Dev Notes
- Railway detects Dockerfile automatically. Use `railway.toml` only if custom settings are needed.
- Port is injected by Railway via `$PORT` environment variable.
- Do NOT commit secrets -- `.env` must be in `.gitignore`.

---

### Story 3.2: Frontend Vercel Deploy

**As a** devops engineer,
**I want** the Next.js frontend deployed to Vercel with correct environment configuration,
**so that** campaign team members can access the dashboard via a URL.

**PRD References**: NFR-007, CON-004, CON-006

#### Acceptance Criteria

1. The `instagram-campaign-web` repository is connected to Vercel as a new project.
2. The following environment variable is configured in Vercel:
   - `NEXT_PUBLIC_API_URL` = the Railway API URL from Story 3.1.
3. Vercel build settings:
   - Framework: Next.js (auto-detected).
   - Build command: `npm run build`.
   - Output directory: auto-detected by Vercel.
4. The frontend builds and deploys successfully on Vercel.
5. All dashboard views load correctly and fetch data from the production API.
6. Navigation between all 7 tabs works without errors.
7. The Vercel deployment URL is documented in the project README.

#### Dev Notes
- Vercel auto-deploys on push to main. Ensure the main branch has the complete frontend code.
- If CORS errors occur, verify the Railway API's `ALLOWED_ORIGINS` includes the Vercel domain.
- Depends on Story 3.1 (API must be deployed first for the frontend to fetch data).

---

### Story 3.3: Production Configuration & Monitoring

**As a** campaign coordinator,
**I want** production-specific configuration applied (CORS, scheduler, logging, health monitoring),
**so that** the system runs securely and reliably during the campaign.

**PRD References**: NFR-002, NFR-005, NFR-006, NFR-008, FR-013, FR-015

#### Acceptance Criteria

1. CORS is locked down: `ALLOWED_ORIGINS` environment variable is set to the Vercel frontend URL. The FastAPI CORS middleware uses this value instead of the development wildcard `"*"`.
2. The application reads `ALLOWED_ORIGINS` as a comma-separated list and configures CORS middleware accordingly.
3. The scheduler is active in production: `SCRAPING_INTERVAL_HOURS` is set to 6 (default) and the APScheduler job is running. Verify by checking the `/health` endpoint's scheduler status field.
4. Structured logging is active: all scraping runs produce log entries with timestamp, level, message, and context fields (candidate, posts_scraped, comments_scraped, duration, errors). Log level is set via `LOG_LEVEL` environment variable (default: INFO).
5. A manual test of the full pipeline is executed in production:
   - Trigger `POST /api/v1/scraping/run`.
   - Verify posts and comments are scraped and stored.
   - Verify sentiment analysis runs.
   - Verify dashboard displays the newly collected data.
6. Health check endpoint `GET /health` returns all required fields: service status, database connectivity, last successful scrape timestamp, scheduler status.
7. A `PRODUCTION-CHECKLIST.md` document is created in the API repo root listing all verified production configurations and their values (without secrets).
8. Railway logs show structured log output from at least one complete scraping cycle.

#### Dev Notes
- CORS change: update `app/main.py` to read from `ALLOWED_ORIGINS` env var and split by comma.
- Do NOT hardcode the Vercel URL -- always read from environment.
- The production test (AC 5) should be performed manually after deployment and documented in the checklist.
- Depends on Stories 3.1 and 3.2 (both services must be deployed).

---

## Definition of Done (Epic Level)

- [ ] API is live on Railway, responding to health checks.
- [ ] Frontend is live on Vercel, all views rendering with production data.
- [ ] CORS is locked to the Vercel domain only.
- [ ] Scheduler is running and has completed at least one full automated cycle.
- [ ] Structured logging produces readable output in Railway logs.
- [ ] Full pipeline (scrape -> analyze -> display) verified end-to-end in production.
- [ ] PRODUCTION-CHECKLIST.md documents all configurations.
- [ ] No secrets are committed to either repository.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Railway free tier memory limits with scheduler | Medium | High | Monitor memory usage; scheduler runs are lightweight if pipeline is sequential |
| CORS misconfiguration blocks frontend | Medium | Medium | Test immediately after deploy; keep wildcard as fallback documented |
| Vercel build fails on first deploy | Low | Low | Build locally first; Vercel provides detailed build logs |
| Apify token exposure in logs | Low | High | Structured logging must never log raw tokens; verify log output |

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0.0 | Initial epic creation | Bob (PM Agent) |

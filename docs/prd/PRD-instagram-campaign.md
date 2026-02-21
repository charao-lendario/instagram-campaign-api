# Instagram Campaign Analytics - Product Requirements Document (PRD)

| Field | Value |
|-------|-------|
| **Product** | Instagram Campaign Analytics |
| **Version** | 1.0.0 |
| **Status** | Draft |
| **Author** | Bob (PM Agent) |
| **Date** | 2026-02-21 |
| **Repos** | API: `instagram-campaign-api` / Web: `instagram-campaign-web` |

---

## 1. Overview

Instagram Campaign Analytics is a web application designed for political campaign teams. It automates the collection, analysis, and visualization of Instagram engagement data for two monitored candidates -- @charlles.evangelista and @delegadasheila -- providing strategic insights that inform campaign decisions.

The system scrapes Instagram posts and comments via Apify actors, runs sentiment analysis (VADER with LLM fallback), stores structured data in Supabase PostgreSQL, exposes analytics through a FastAPI backend, and presents everything in a Next.js dashboard with comparative visualizations.

---

## 2. Problem Statement

Political campaigns need real-time visibility into public sentiment expressed on Instagram to adjust messaging strategy. Currently, campaign teams manually scan comments across candidate profiles, which is:

- **Slow**: Hundreds of comments across dozens of posts cannot be processed manually in useful timeframes.
- **Subjective**: Without systematic classification, sentiment assessment depends on who is reading.
- **Non-comparative**: There is no structured way to compare engagement patterns between the campaign's candidate and the opponent.
- **Non-actionable**: Raw comments do not surface thematic patterns or strategic opportunities.

This application solves these problems by automating data collection, applying consistent sentiment classification, and generating visual comparisons and AI-driven strategic suggestions.

---

## 3. Target Users

| Persona | Description | Primary Need |
|---------|-------------|--------------|
| **Campaign Strategist** | Senior team member making messaging decisions | Comparative sentiment trends, strategic suggestions |
| **Social Media Manager** | Manages candidate's Instagram presence | Post-level engagement metrics, theme analysis |
| **Campaign Coordinator** | Oversees daily operations | High-level dashboard, alerting on sentiment shifts |

All users access the system through the web dashboard. There are no public-facing users -- this is an internal campaign tool.

---

## 4. Goals

- Automate Instagram data collection for both monitored candidates with periodic scheduling.
- Provide accurate sentiment classification (positive/negative/neutral) for every comment collected.
- Enable side-by-side comparison of candidates across engagement and sentiment metrics.
- Surface recurring themes in public discourse to identify strategic opportunities.
- Generate AI-powered strategic suggestions grounded in real engagement data.
- Deliver all insights through a responsive, intuitive dashboard.

---

## 5. Background Context

The application targets the Brazilian political campaign context where Instagram is a primary channel for candidate communication and public engagement. The two monitored profiles -- @charlles.evangelista and @delegadasheila -- represent the campaign's candidate and a key opponent. The system must handle Portuguese-language content for sentiment analysis and theme extraction.

The technical approach uses Apify's managed scraping infrastructure to avoid the complexity of direct Instagram API integration (which requires Meta Business review and has strict rate limits). VADER provides fast baseline sentiment scoring, with LLM fallback for ambiguous cases or Portuguese-specific nuance. The polyrepo structure separates the API (FastAPI on Railway) from the frontend (Next.js on Vercel), connected through REST endpoints.

---

## 6. Functional Requirements

### FR-001: Instagram Post Scraping
The system shall scrape the latest 10 posts from each monitored candidate profile (@charlles.evangelista, @delegadasheila) using the Apify `instagram-post-scraper` actor. Each post record must include: post URL, caption, timestamp, like count, comment count, and media type.

### FR-002: Instagram Comment Scraping
The system shall scrape all comments from each scraped post using the Apify `instagram-comment-scraper` actor. Each comment record must include: comment text, author username, timestamp, like count, and parent post reference.

### FR-003: Sentiment Analysis (VADER Primary)
The system shall classify each comment as positive, negative, or neutral using the VADER sentiment analyzer. The compound score threshold shall be: positive >= 0.05, negative <= -0.05, neutral otherwise. Each comment record must store the compound score and the classification label.

### FR-004: Sentiment Analysis (LLM Fallback)
When VADER's compound score falls within an ambiguous range (-0.05 < score < 0.05 and text length > 20 characters), the system shall use an LLM API call to reclassify the comment with a confidence score. The LLM provider and model shall be configurable via environment variables.

### FR-005: Data Persistence
The system shall persist all scraped posts, comments, sentiment scores, and derived analytics to Supabase PostgreSQL. The schema must enforce referential integrity between candidates, posts, and comments.

### FR-006: Overview Dashboard
The frontend shall display an overview dashboard showing key engagement metrics for both candidates side by side: total posts scraped, total comments, average sentiment score, sentiment distribution (positive/negative/neutral counts), and total engagement (likes + comments).

### FR-007: Temporal Sentiment Chart
The frontend shall display a line chart showing sentiment score evolution over time, with one series per candidate. The x-axis represents post timestamps, and the y-axis represents average sentiment score per post. The user shall be able to filter by date range.

### FR-008: Word Cloud
The frontend shall display a word cloud visualization of the most frequent words in comments. The user shall be able to filter by candidate. Common stop words in Portuguese must be excluded.

### FR-009: Recurring Themes
The system shall group comments into thematic categories (e.g., health, security, education, economy, infrastructure). Theme extraction shall use keyword-based classification with LLM enrichment for ambiguous comments. The frontend shall display theme distribution per candidate.

### FR-010: Post Comparison
The frontend shall display a ranked list of posts ordered by engagement metrics (total comments, positive ratio, negative ratio). The user shall be able to sort by different metrics and filter by candidate.

### FR-011: Candidate Comparison
The frontend shall display a dedicated comparison view with side-by-side metrics for both candidates: sentiment distribution, top themes, engagement averages, and trend direction (improving/declining sentiment).

### FR-012: Strategic Suggestions
The system shall generate AI-powered strategic suggestions based on collected data. Suggestions must reference specific data points (e.g., "Opponent's posts about security generate 40% more positive engagement -- consider addressing security themes"). The backend endpoint shall accept the current dataset summary and return 3-5 actionable suggestions.

### FR-013: Automated Scheduling
The system shall support periodic automated scraping via APScheduler. The default schedule shall be configurable (default: every 6 hours). The scheduler must prevent concurrent runs and log execution results.

### FR-014: Manual Scraping Trigger
The system shall expose an API endpoint to trigger an immediate scraping run on demand, independent of the scheduler.

### FR-015: API Health Check
The system shall expose a `/health` endpoint returning service status, database connectivity status, and last successful scraping timestamp.

---

## 7. Non-Functional Requirements

### NFR-001: Response Time
API endpoints shall respond within 2 seconds for data retrieval operations. Scraping trigger endpoints may take longer but must return an acknowledgment within 1 second.

### NFR-002: Data Freshness
With the default 6-hour schedule, dashboard data shall never be more than 7 hours stale under normal operation.

### NFR-003: Portuguese Language Support
Sentiment analysis and theme extraction must handle Portuguese-language content correctly. VADER's English bias is acceptable for baseline scoring; the LLM fallback must be prompted in Portuguese for reclassification.

### NFR-004: Scalability
The system shall handle up to 10 posts x 2 candidates x ~500 comments per post (10,000 comments total) without performance degradation. Database queries must use appropriate indexes.

### NFR-005: Error Resilience
Apify actor failures shall not crash the application. Failed scraping runs must be logged with error details and retried on the next schedule cycle. Partial data collection (one candidate succeeds, another fails) must be preserved.

### NFR-006: Security
API endpoints shall not expose raw Apify tokens or database credentials. Environment variables must be used for all secrets. CORS must be configured to allow only the frontend domain in production.

### NFR-007: Deployment
The API must be deployable to Railway via Docker. The frontend must be deployable to Vercel. Both deployments must support environment variable injection.

### NFR-008: Observability
The API shall log all scraping runs (start time, end time, records collected, errors) with structured logging. Log level shall be configurable via environment variable.

### NFR-009: Cost Efficiency
Apify usage must be optimized to minimize actor run costs. Each scraping cycle should use a maximum of 2 actor runs (one for posts, one for comments per candidate, total 4 runs per cycle).

### NFR-010: Code Quality
Python code must follow PEP 8. Type hints are required for all function signatures. Pydantic models must be used for all request/response schemas.

---

## 8. Constraints

### CON-001: Instagram Access
Instagram scraping is performed exclusively through Apify actors. Direct Instagram API or browser automation is out of scope.

### CON-002: Monitored Profiles
The MVP monitors exactly two profiles: @charlles.evangelista and @delegadasheila. Adding new profiles is out of scope for MVP.

### CON-003: Tech Stack (Backend)
Python 3.11+, FastAPI, apify-client, vaderSentiment, Supabase Python client, APScheduler, Pydantic. No ORM -- use Supabase client directly.

### CON-004: Tech Stack (Frontend)
Next.js 16, Tailwind CSS, shadcn/ui, Recharts for charts. No additional charting libraries.

### CON-005: Database
Supabase PostgreSQL. No Row-Level Security required for MVP (internal tool). Standard PostgreSQL indexes and constraints.

### CON-006: Hosting
API on Railway (Docker-based). Frontend on Vercel. No self-hosted infrastructure.

### CON-007: Repository Structure
Polyrepo: `instagram-campaign-api` (FastAPI backend) and `instagram-campaign-web` (Next.js frontend) are separate repositories.

### CON-008: LLM Provider
LLM provider for fallback sentiment analysis and strategic suggestions must be configurable via environment variable (provider + model + API key). Default: OpenAI GPT-4o-mini.

### CON-009: Budget
Apify free tier or minimal paid tier. Railway free tier. Vercel free tier. LLM costs must be minimized by using VADER as primary analyzer and LLM only as fallback.

### CON-010: Timeline
MVP must be deliverable within 2-3 weeks of development effort.

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data Collection Reliability | >= 95% of scheduled scraping runs complete successfully | Monitoring logs over 7 days |
| Sentiment Accuracy | >= 80% agreement with manual classification on 50-sample validation | Manual spot-check |
| Dashboard Load Time | < 3 seconds for initial page load | Lighthouse / manual measurement |
| Strategic Suggestion Quality | >= 3 out of 5 suggestions rated "actionable" by campaign team | User feedback |
| Data Freshness | Data never > 7 hours stale | Dashboard timestamp check |
| System Uptime | >= 99% during campaign period | Railway/Vercel monitoring |

---

## 10. Scope Boundaries

### In Scope (MVP)
- Scraping posts and comments for 2 fixed candidate profiles
- VADER sentiment analysis with LLM fallback
- Overview dashboard with side-by-side metrics
- Temporal sentiment chart (line chart)
- Word cloud with candidate filter
- Theme grouping (keyword + LLM)
- Post comparison ranking
- Candidate comparison view
- AI strategic suggestions
- Automated scheduler (configurable interval)
- Manual scraping trigger
- Docker deployment for API

### Out of Scope (Future)
- User authentication and multi-tenancy
- Adding/removing monitored profiles via UI
- Real-time WebSocket updates
- Instagram Stories or Reels analysis
- Comment reply threading analysis
- Export to PDF/CSV
- Email/push notifications on sentiment shifts
- Historical data backfill beyond current scraping window
- Mobile native app
- Multi-language support beyond Portuguese

---

## 11. User Interface Design Goals

### 11.1 Overall UX Vision
A clean, data-dense dashboard optimized for quick decision-making. The primary interaction pattern is a single-page dashboard with tab-based navigation between views. Dark mode support is not required for MVP.

### 11.2 Key Interaction Paradigms
- **Comparison-first**: Every view defaults to showing both candidates side by side.
- **Filter-and-drill**: Global candidate filter with drill-down to individual posts.
- **Glanceable metrics**: Key numbers (sentiment score, engagement) visible without scrolling.

### 11.3 Core Screens
1. **Overview Dashboard** -- Side-by-side candidate metrics, sentiment summary, recent activity.
2. **Sentiment Timeline** -- Line chart with date range picker.
3. **Word Cloud** -- Interactive word cloud with candidate toggle.
4. **Themes** -- Bar/pie chart showing theme distribution per candidate.
5. **Post Comparison** -- Sortable table of posts with engagement metrics.
6. **Strategic Insights** -- AI-generated suggestions with supporting data points.

### 11.4 Accessibility
WCAG AA basic compliance. Sufficient color contrast, keyboard navigation for controls, alt text for charts.

### 11.5 Branding
Campaign brand colors to be defined by user. Default: neutral palette (slate/blue). No specific logo or brand guide provided.

### 11.6 Target Platforms
Web Responsive (desktop primary, tablet secondary). Mobile support is not a priority for MVP.

---

## 12. Technical Assumptions

### 12.1 Repository Structure
Polyrepo: Two separate repositories, each independently deployable.

### 12.2 Service Architecture
Two-tier: FastAPI REST API (backend) + Next.js static/SSR (frontend). No microservices, no message queues. Frontend calls backend API directly.

### 12.3 Testing Requirements
- **Backend**: Unit tests for sentiment analysis logic, service layer, and API endpoints. Integration tests for Apify client mocking and Supabase operations.
- **Frontend**: Component tests for dashboard widgets. No E2E tests for MVP.
- **Framework**: pytest (backend), Jest + React Testing Library (frontend).

### 12.4 Additional Technical Assumptions
- Apify actors are called via the `apify-client` Python SDK, not via HTTP directly.
- Supabase is accessed via the official `supabase-py` client, not via raw SQL connections.
- APScheduler runs in-process with the FastAPI application (no external task queue).
- LLM calls use `httpx` for async HTTP requests to the provider's API.
- Frontend fetches data from the API using `fetch` or a lightweight client (no Redux, no complex state management).
- Recharts is the sole charting library. Word cloud may use a dedicated React component library (e.g., `react-wordcloud`).

---

## 13. Epics Overview

### Epic 1: Backend (FastAPI + Apify) -- 7 Stories
**Goal**: Build the complete backend API that scrapes Instagram data, performs sentiment analysis, persists data to Supabase, and exposes all necessary endpoints for the frontend dashboard.

| Story | Title | Summary |
|-------|-------|---------|
| 1.1 | Database Schema & Supabase Setup | Create tables for candidates, posts, comments, sentiment scores |
| 1.2 | Apify Post Scraping Service | Implement post scraping via Apify instagram-post-scraper |
| 1.3 | Apify Comment Scraping Service | Implement comment scraping via Apify instagram-comment-scraper |
| 1.4 | VADER Sentiment Analysis | Classify comments using VADER with score storage |
| 1.5 | LLM Fallback Sentiment Analysis | Reclassify ambiguous comments via configurable LLM |
| 1.6 | Analytics & Comparison Endpoints | Endpoints for dashboard metrics, themes, post ranking, candidate comparison |
| 1.7 | Scheduler & Strategic Suggestions | APScheduler for periodic scraping + LLM strategic suggestions endpoint |

### Epic 2: Frontend (Next.js Dashboard) -- 8 Stories
**Goal**: Build the responsive dashboard that visualizes all analytics data from the API, enabling campaign strategists to compare candidates, track sentiment trends, and act on AI-generated suggestions.

| Story | Title | Summary |
|-------|-------|---------|
| 2.1 | Project Setup & Layout Shell | Next.js scaffolding, Tailwind, shadcn/ui, layout with navigation |
| 2.2 | API Client & Data Fetching | Typed API client, SWR/fetch hooks for all backend endpoints |
| 2.3 | Overview Dashboard | Side-by-side candidate metrics cards and summary stats |
| 2.4 | Sentiment Timeline Chart | Recharts line chart with date range filtering |
| 2.5 | Word Cloud Visualization | Interactive word cloud with candidate filter |
| 2.6 | Theme Analysis View | Theme distribution charts per candidate |
| 2.7 | Post & Candidate Comparison | Sortable post table and dedicated comparison view |
| 2.8 | Strategic Insights View | AI suggestions display with data point references |

### Epic 3: Infra & Deploy -- 3 Stories
**Goal**: Containerize, deploy, and configure production infrastructure for both API and frontend, ensuring reliable operation with proper monitoring.

| Story | Title | Summary |
|-------|-------|---------|
| 3.1 | API Dockerization & Railway Deploy | Dockerfile optimization, Railway service configuration, env vars |
| 3.2 | Frontend Vercel Deploy | Vercel project setup, environment configuration, build optimization |
| 3.3 | Production Configuration & Monitoring | CORS lockdown, scheduler activation, health monitoring, logging |

---

## 14. Data Model (High-Level)

```
candidates
  - id (UUID, PK)
  - username (TEXT, UNIQUE)
  - display_name (TEXT)
  - created_at (TIMESTAMPTZ)

posts
  - id (UUID, PK)
  - candidate_id (UUID, FK -> candidates)
  - instagram_id (TEXT, UNIQUE)
  - url (TEXT)
  - caption (TEXT)
  - like_count (INTEGER)
  - comment_count (INTEGER)
  - media_type (TEXT)
  - posted_at (TIMESTAMPTZ)
  - scraped_at (TIMESTAMPTZ)

comments
  - id (UUID, PK)
  - post_id (UUID, FK -> posts)
  - instagram_id (TEXT, UNIQUE)
  - text (TEXT)
  - author_username (TEXT)
  - like_count (INTEGER)
  - commented_at (TIMESTAMPTZ)
  - scraped_at (TIMESTAMPTZ)

sentiment_scores
  - id (UUID, PK)
  - comment_id (UUID, FK -> comments, UNIQUE)
  - vader_compound (FLOAT)
  - vader_label (TEXT)
  - llm_label (TEXT, NULLABLE)
  - llm_confidence (FLOAT, NULLABLE)
  - final_label (TEXT)
  - analyzed_at (TIMESTAMPTZ)

scraping_runs
  - id (UUID, PK)
  - started_at (TIMESTAMPTZ)
  - completed_at (TIMESTAMPTZ, NULLABLE)
  - status (TEXT)
  - posts_scraped (INTEGER)
  - comments_scraped (INTEGER)
  - errors (JSONB, NULLABLE)

themes
  - id (UUID, PK)
  - comment_id (UUID, FK -> comments)
  - theme (TEXT)
  - confidence (FLOAT)
  - method (TEXT)
```

---

## 15. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Apify actor rate limits or blocks | Medium | High | Implement retry logic with exponential backoff; monitor actor run status; keep scraping frequency conservative (6h default) |
| VADER inaccuracy for Portuguese | High | Medium | LLM fallback for ambiguous cases; validate accuracy with manual sample; consider fine-tuning threshold |
| Instagram profile changes (username, privacy) | Low | High | Store Instagram IDs alongside usernames; add error alerting for failed scrapes |
| Supabase free tier limits | Low | Medium | Monitor usage; optimize queries with indexes; consider upgrading if needed |
| LLM API costs exceed budget | Medium | Medium | Use VADER as primary (free); LLM only for ambiguous subset; set monthly cost cap |
| Railway free tier resource limits | Medium | Medium | Optimize Docker image size; monitor resource usage; scheduler prevents concurrent runs |

---

## 16. Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0.0 | Initial PRD creation | Bob (PM Agent) |

---

## 17. Next Steps

### Architect Prompt
Review the PRD at `docs/prd/PRD-instagram-campaign.md` and create the system architecture document. Focus on: API route structure, service layer design, Supabase schema DDL, Apify integration patterns, and the sentiment analysis pipeline. Reference all FR/NFR/CON identifiers in design decisions.

### UX Expert Prompt
Review the PRD at `docs/prd/PRD-instagram-campaign.md` (sections 11 and Epic 2 stories) and create the frontend specification. Focus on: component hierarchy, dashboard layout, chart configurations, responsive breakpoints, and shadcn/ui component selection. Reference Core Screens (section 11.3) for view definitions.

# Instagram Campaign Analytics -- System Architecture Document

| Field | Value |
|-------|-------|
| **Product** | Instagram Campaign Analytics |
| **Version** | 1.0.0 |
| **Status** | Draft |
| **Author** | Aria (Architect Agent) |
| **Date** | 2026-02-21 |
| **PRD** | `docs/prd/PRD-instagram-campaign.md` |
| **Repositories** | API: `instagram-campaign-api` / Web: `instagram-campaign-web` |

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Architecture](#2-component-architecture)
3. [API Design](#3-api-design)
4. [Data Flow](#4-data-flow)
5. [Database Schema](#5-database-schema)
6. [Integration Points](#6-integration-points)
7. [Security Considerations](#7-security-considerations)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Technology Decisions](#9-technology-decisions)
10. [Non-Functional Requirements Mapping](#10-non-functional-requirements-mapping)
11. [Change Log](#11-change-log)

---

## 1. System Overview

### 1.1 Context Diagram

```
+------------------------------+
|     Campaign Strategist      |
|     Social Media Manager     |
|     Campaign Coordinator     |
+-------------+----------------+
              |
              | HTTPS (browser)
              v
+-------------+----------------+
|                              |
|   instagram-campaign-web     |
|   (Next.js 16 / Vercel)     |
|                              |
|   - Overview Dashboard       |
|   - Sentiment Timeline       |
|   - Word Cloud               |
|   - Theme Analysis           |
|   - Post Comparison          |
|   - Candidate Comparison     |
|   - Strategic Insights       |
|                              |
+-------------+----------------+
              |
              | HTTPS REST API
              v
+-------------+----------------+
|                              |
|   instagram-campaign-api     |
|   (FastAPI / Railway)        |
|                              |
|   - Scraping orchestration   |
|   - Sentiment analysis       |
|   - Theme extraction         |
|   - Analytics aggregation    |
|   - Strategic suggestions    |
|   - Scheduler (APScheduler)  |
|                              |
+---+--------+---------+------+
    |        |         |
    v        v         v
+-------+ +--------+ +----------+
| Apify | |Supabase| | LLM API  |
| Cloud | |  PgSQL | | (OpenAI) |
+-------+ +--------+ +----------+
  |                       |
  v                       v
Instagram            GPT-4o-mini
(public profiles)    (fallback sentiment
                      + suggestions)
```

### 1.2 System Boundaries

| Boundary | Internal / External | Protocol |
|----------|-------------------|----------|
| Frontend <-> API | Internal (polyrepo, same team) | HTTPS REST (JSON) |
| API <-> Supabase | Internal (managed service) | HTTPS (supabase-py SDK) |
| API <-> Apify | External (third-party) | HTTPS (apify-client SDK) |
| API <-> LLM Provider | External (third-party) | HTTPS (httpx) |
| Apify <-> Instagram | External (third-party, scraped) | Managed by Apify |

### 1.3 Key Architectural Decisions

| Decision | Choice | PRD Reference |
|----------|--------|---------------|
| Architecture style | Two-tier (API + SPA), no microservices | CON-007, 12.2 |
| Data access | Supabase Python SDK, no ORM | CON-003 |
| Scraping | Apify managed actors, not direct API | CON-001 |
| Scheduling | In-process APScheduler, no external queue | 12.4 |
| State management (FE) | No Redux/Zustand, fetch + hooks | 12.4 |
| Repo structure | Polyrepo (API + Web separate) | CON-007 |

---

## 2. Component Architecture

### 2.1 Backend Component Diagram (instagram-campaign-api)

```
instagram-campaign-api/
|
+-- app/
|   +-- main.py                  # FastAPI app, CORS, lifespan (scheduler)
|   +-- core/
|   |   +-- config.py            # pydantic-settings, env vars
|   |   +-- constants.py         # Stop words, theme keywords, thresholds
|   |   +-- logging.py           # Structured logging setup
|   |
|   +-- db/
|   |   +-- supabase.py          # Supabase client singleton
|   |
|   +-- models/
|   |   +-- candidate.py         # Candidate Pydantic model
|   |   +-- post.py              # Post Pydantic model
|   |   +-- comment.py           # Comment Pydantic model
|   |   +-- sentiment.py         # SentimentScore, SentimentResult models
|   |   +-- theme.py             # Theme Pydantic model
|   |   +-- scraping.py          # ScrapingRun model
|   |   +-- analytics.py         # Response models (Overview, Timeline, etc.)
|   |   +-- suggestion.py        # Strategic suggestion model
|   |
|   +-- services/
|   |   +-- scraping.py          # Apify post/comment scraping
|   |   +-- sentiment.py         # VADER + LLM fallback analysis
|   |   +-- themes.py            # Keyword + LLM theme extraction
|   |   +-- analytics.py         # Aggregation queries for dashboard
|   |   +-- suggestions.py       # LLM strategic suggestion generation
|   |   +-- pipeline.py          # Full pipeline orchestration
|   |
|   +-- routers/
|   |   +-- health.py            # GET /health
|   |   +-- scraping.py          # POST scraping triggers
|   |   +-- analysis.py          # POST sentiment/theme analysis triggers
|   |   +-- analytics.py         # GET dashboard data endpoints
|   |   +-- suggestions.py       # POST strategic suggestions
|   |
|   +-- scheduler/
|       +-- jobs.py              # APScheduler job definitions
|       +-- lock.py              # Concurrency lock (threading.Lock)
|
+-- tests/
|   +-- test_scraping.py
|   +-- test_sentiment.py
|   +-- test_themes.py
|   +-- test_analytics.py
|   +-- test_pipeline.py
|   +-- conftest.py              # Shared fixtures, mocked Supabase/Apify
|
+-- docs/
|   +-- architecture/
|       +-- architecture.md      # This document
|       +-- migrations/
|           +-- 001_initial_schema.sql
|
+-- Dockerfile
+-- requirements.txt
+-- .env.example
+-- railway.toml
```

### 2.2 Backend Layer Architecture

```
+-----------------------------------------------------------+
|                     ROUTER LAYER                          |
|  health.py | scraping.py | analysis.py | analytics.py    |
|  suggestions.py                                           |
+-----------------------------------------------------------+
                          |
                     Pydantic models
                     (request/response validation)
                          |
+-----------------------------------------------------------+
|                    SERVICE LAYER                          |
|  scraping.py | sentiment.py | themes.py | analytics.py  |
|  suggestions.py | pipeline.py                             |
+-----------------------------------------------------------+
                          |
                  Supabase SDK calls
                          |
+-----------------------------------------------------------+
|                   DATA ACCESS LAYER                       |
|             db/supabase.py (client singleton)             |
+-----------------------------------------------------------+
                          |
+-----------------------------------------------------------+
|              SUPABASE POSTGRESQL                          |
|  candidates | posts | comments | sentiment_scores        |
|  themes | scraping_runs                                   |
+-----------------------------------------------------------+
```

**Design rationale:** The three-layer separation (Router -> Service -> Data) keeps business logic in services, HTTP concerns in routers, and data access isolated behind the Supabase client. No ORM is used per CON-003; the `supabase-py` client handles all database operations directly.

### 2.3 Frontend Component Hierarchy (instagram-campaign-web)

```
instagram-campaign-web/
|
+-- app/
|   +-- layout.tsx               # Root layout: header, nav tabs, CandidateFilter
|   +-- overview/page.tsx        # Overview dashboard
|   +-- sentiment/page.tsx       # Sentiment timeline chart
|   +-- words/page.tsx           # Word cloud
|   +-- themes/page.tsx          # Theme analysis
|   +-- posts/page.tsx           # Post comparison table
|   +-- comparison/page.tsx      # Candidate comparison
|   +-- insights/page.tsx        # Strategic insights
|
+-- components/
|   +-- layout/
|   |   +-- header.tsx           # App header with title
|   |   +-- nav-tabs.tsx         # Tab navigation
|   |   +-- candidate-filter.tsx # Global candidate toggle
|   |
|   +-- dashboard/
|   |   +-- metric-card.tsx      # Reusable metric display card
|   |   +-- sentiment-badge.tsx  # Color-coded sentiment indicator
|   |   +-- summary-row.tsx      # Aggregate totals row
|   |
|   +-- charts/
|   |   +-- sentiment-line.tsx   # Recharts line chart wrapper
|   |   +-- theme-bar.tsx        # Recharts bar chart wrapper
|   |   +-- theme-pie.tsx        # Recharts pie chart wrapper
|   |   +-- sparkline.tsx        # Mini chart for comparison view
|   |
|   +-- shared/
|       +-- loading-skeleton.tsx # Shimmer loading placeholder
|       +-- error-message.tsx    # User-friendly error display
|       +-- empty-state.tsx      # No-data message with action
|
+-- lib/
|   +-- api.ts                   # Typed API client functions
|   +-- types.ts                 # TypeScript interfaces (mirrors Pydantic)
|   +-- constants.ts             # Color config, API base URL
|
+-- hooks/
|   +-- use-overview.ts
|   +-- use-sentiment-timeline.ts
|   +-- use-word-cloud.ts
|   +-- use-themes.ts
|   +-- use-posts.ts
|   +-- use-comparison.ts
|   +-- use-suggestions.ts
|   +-- use-health.ts
```

---

## 3. API Design

### 3.1 Base Configuration

| Property | Value |
|----------|-------|
| Base URL | `https://{railway-domain}` |
| API Prefix | `/api/v1` |
| Content-Type | `application/json` |
| Authentication | None (internal tool, MVP) |
| Versioning | URL path (`/api/v1/`) |
| Docs | Auto-generated at `/docs` (Swagger UI) |

### 3.2 Endpoint Reference

#### 3.2.1 Health

**`GET /health`**

Returns service health, database status, scheduler state, and last scrape timestamp.

PRD: FR-015

Request: No parameters.

Response `200 OK`:
```json
{
  "status": "ok",
  "database": "connected",
  "scheduler": "running",
  "last_scrape": "2026-02-21T14:00:00Z"
}
```

Response `503 Service Unavailable`:
```json
{
  "status": "degraded",
  "database": "disconnected",
  "scheduler": "stopped",
  "last_scrape": null
}
```

---

#### 3.2.2 Scraping

**`POST /api/v1/scraping/posts`**

Triggers post scraping for all monitored candidates.

PRD: FR-001

Request: No body.

Response `202 Accepted`:
```json
{
  "run_id": "uuid",
  "status": "started",
  "candidates": ["charlles.evangelista", "delegadasheila"]
}
```

---

**`POST /api/v1/scraping/comments`**

Triggers comment scraping for all scraped posts that need comment collection.

PRD: FR-002

Request: No body.

Response `202 Accepted`:
```json
{
  "run_id": "uuid",
  "status": "started",
  "posts_queued": 20
}
```

---

**`POST /api/v1/scraping/run`**

Triggers the full pipeline: posts -> comments -> VADER -> LLM fallback -> themes.

PRD: FR-014

Request: No body.

Response `202 Accepted`:
```json
{
  "run_id": "uuid",
  "status": "started",
  "message": "Full pipeline initiated"
}
```

Response `409 Conflict`:
```json
{
  "detail": "Pipeline already in progress",
  "current_run_id": "uuid"
}
```

---

#### 3.2.3 Analysis

**`POST /api/v1/analysis/sentiment`**

Triggers VADER sentiment analysis for all unanalyzed comments.

PRD: FR-003

Request: No body.

Response `200 OK`:
```json
{
  "analyzed_count": 342,
  "skipped_count": 58,
  "message": "Sentiment analysis complete"
}
```

---

**`GET /api/v1/analysis/sentiment/summary`**

Returns aggregate sentiment counts for a candidate.

PRD: FR-003

Query Parameters:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `candidate_id` | UUID | Yes | Candidate to aggregate |

Response `200 OK`:
```json
{
  "candidate_id": "uuid",
  "candidate_username": "charlles.evangelista",
  "total_comments": 500,
  "positive_count": 210,
  "negative_count": 140,
  "neutral_count": 150,
  "average_compound_score": 0.12
}
```

---

**`POST /api/v1/analysis/sentiment/llm-fallback`**

Triggers LLM reclassification for ambiguous comments.

PRD: FR-004

Request: No body.

Response `200 OK`:
```json
{
  "reclassified_count": 47,
  "api_calls_made": 47,
  "confidence_upgrades": 32,
  "retained_vader_label": 15
}
```

---

#### 3.2.4 Analytics (Dashboard Data)

**`GET /api/v1/analytics/overview`**

Returns overview metrics for all candidates, side by side.

PRD: FR-006

Request: No parameters.

Response `200 OK`:
```json
{
  "candidates": [
    {
      "candidate_id": "uuid",
      "username": "charlles.evangelista",
      "display_name": "Charlles Evangelista",
      "total_posts": 10,
      "total_comments": 487,
      "average_sentiment_score": 0.15,
      "sentiment_distribution": {
        "positive": 210,
        "negative": 127,
        "neutral": 150
      },
      "total_engagement": 3542
    },
    {
      "candidate_id": "uuid",
      "username": "delegadasheila",
      "display_name": "Delegada Sheila",
      "total_posts": 10,
      "total_comments": 523,
      "average_sentiment_score": -0.03,
      "sentiment_distribution": {
        "positive": 180,
        "negative": 198,
        "neutral": 145
      },
      "total_engagement": 4120
    }
  ],
  "last_scrape": "2026-02-21T14:00:00Z",
  "total_comments_analyzed": 1010
}
```

---

**`GET /api/v1/analytics/sentiment-timeline`**

Returns temporal sentiment data points per post, with optional date filtering.

PRD: FR-007

Query Parameters:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `candidate_id` | UUID | No | All | Filter by candidate |
| `start_date` | ISO date | No | 30 days ago | Start of date range |
| `end_date` | ISO date | No | Today | End of date range |

Response `200 OK`:
```json
{
  "data_points": [
    {
      "candidate_id": "uuid",
      "candidate_username": "charlles.evangelista",
      "post_id": "uuid",
      "post_url": "https://instagram.com/p/abc123",
      "post_caption": "Hoje visitamos o bairro...",
      "posted_at": "2026-02-15T10:30:00Z",
      "average_sentiment_score": 0.23,
      "comment_count": 45
    }
  ]
}
```

---

**`GET /api/v1/analytics/wordcloud`**

Returns word frequency data for word cloud rendering.

PRD: FR-008

Query Parameters:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `candidate_id` | UUID | No | All | Filter by candidate |

Response `200 OK`:
```json
{
  "words": [
    { "word": "saude", "count": 87 },
    { "word": "seguranca", "count": 65 },
    { "word": "prefeito", "count": 52 }
  ],
  "total_unique_words": 342
}
```

---

**`GET /api/v1/analytics/themes`**

Returns theme distribution data.

PRD: FR-009

Query Parameters:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `candidate_id` | UUID | No | All | Filter by candidate |

Response `200 OK`:
```json
{
  "themes": [
    {
      "theme": "saude",
      "count": 87,
      "percentage": 17.2,
      "by_candidate": [
        { "candidate_id": "uuid", "username": "charlles.evangelista", "count": 52 },
        { "candidate_id": "uuid", "username": "delegadasheila", "count": 35 }
      ]
    },
    {
      "theme": "seguranca",
      "count": 65,
      "percentage": 12.8,
      "by_candidate": [
        { "candidate_id": "uuid", "username": "charlles.evangelista", "count": 28 },
        { "candidate_id": "uuid", "username": "delegadasheila", "count": 37 }
      ]
    }
  ]
}
```

---

**`GET /api/v1/analytics/posts`**

Returns a ranked list of posts with engagement metrics.

PRD: FR-010

Query Parameters:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `candidate_id` | UUID | No | All | Filter by candidate |
| `sort_by` | string | No | `comment_count` | Sort metric: `comment_count`, `like_count`, `positive_ratio`, `negative_ratio`, `sentiment_score` |
| `order` | string | No | `desc` | Sort order: `asc` or `desc` |
| `limit` | int | No | 20 | Results per page |
| `offset` | int | No | 0 | Pagination offset |

Response `200 OK`:
```json
{
  "posts": [
    {
      "post_id": "uuid",
      "candidate_username": "charlles.evangelista",
      "url": "https://instagram.com/p/abc123",
      "caption": "Hoje visitamos o bairro...",
      "posted_at": "2026-02-15T10:30:00Z",
      "like_count": 234,
      "comment_count": 87,
      "positive_ratio": 0.48,
      "negative_ratio": 0.22,
      "average_sentiment_score": 0.19
    }
  ],
  "total": 20,
  "limit": 20,
  "offset": 0
}
```

---

**`GET /api/v1/analytics/comparison`**

Returns side-by-side candidate comparison with trend analysis.

PRD: FR-011

Request: No parameters.

Response `200 OK`:
```json
{
  "candidates": [
    {
      "candidate_id": "uuid",
      "username": "charlles.evangelista",
      "display_name": "Charlles Evangelista",
      "total_posts": 10,
      "total_comments": 487,
      "average_sentiment_score": 0.15,
      "total_engagement": 3542,
      "sentiment_distribution": {
        "positive": 210,
        "negative": 127,
        "neutral": 150
      },
      "top_themes": [
        { "theme": "saude", "count": 52 },
        { "theme": "educacao", "count": 38 },
        { "theme": "seguranca", "count": 28 }
      ],
      "trend": {
        "direction": "improving",
        "recent_avg": 0.21,
        "previous_avg": 0.09,
        "delta": 0.12
      }
    },
    {
      "candidate_id": "uuid",
      "username": "delegadasheila",
      "display_name": "Delegada Sheila",
      "total_posts": 10,
      "total_comments": 523,
      "average_sentiment_score": -0.03,
      "total_engagement": 4120,
      "sentiment_distribution": {
        "positive": 180,
        "negative": 198,
        "neutral": 145
      },
      "top_themes": [
        { "theme": "seguranca", "count": 37 },
        { "theme": "corrupcao", "count": 29 },
        { "theme": "economia", "count": 24 }
      ],
      "trend": {
        "direction": "declining",
        "recent_avg": -0.08,
        "previous_avg": 0.02,
        "delta": -0.10
      }
    }
  ]
}
```

**Trend calculation logic:** `recent_avg` is computed from the average sentiment of the last 5 posts, `previous_avg` from the 5 posts before those. `direction` is `"improving"` when `delta > 0`, `"declining"` when `delta < 0`, and `"stable"` when `|delta| < 0.02`.

---

#### 3.2.5 Strategic Suggestions

**`POST /api/v1/analytics/suggestions`**

Generates AI-powered strategic suggestions based on current data.

PRD: FR-012

Request Body (optional):
```json
{
  "candidate_id": "uuid"
}
```

Response `200 OK`:
```json
{
  "suggestions": [
    {
      "title": "Explorar tema de saude com mais frequencia",
      "description": "Posts do candidato sobre saude geram 40% mais engajamento positivo que a media. A adversaria tem presenca fraca neste tema.",
      "supporting_data": "Charlles: 52 comentarios sobre saude (82% positivos) vs Sheila: 35 (61% positivos)",
      "priority": "high"
    },
    {
      "title": "Responder ao dominio da adversaria em seguranca",
      "description": "Delegada Sheila domina o tema seguranca com sentiment positivo. Considere articular proposta concreta de seguranca.",
      "supporting_data": "Sheila: 37 comentarios sobre seguranca (avg score 0.31) vs Charlles: 28 (avg score 0.08)",
      "priority": "high"
    },
    {
      "title": "Manter ritmo de publicacao",
      "description": "O candidato esta com tendencia de melhora no sentimento. Manter consistencia de publicacao consolida essa tendencia.",
      "supporting_data": "Ultimos 5 posts: avg sentiment 0.21 (melhora de +0.12 vs periodo anterior)",
      "priority": "medium"
    }
  ],
  "generated_at": "2026-02-21T15:30:00Z",
  "data_snapshot": {
    "total_comments_analyzed": 1010,
    "last_scrape": "2026-02-21T14:00:00Z"
  }
}
```

---

### 3.3 Error Response Format

All endpoints follow a consistent error format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2026-02-21T15:30:00Z"
}
```

Standard HTTP status codes:

| Code | Usage |
|------|-------|
| 200 | Successful retrieval or synchronous action |
| 202 | Accepted (async pipeline trigger) |
| 400 | Invalid parameters |
| 404 | Resource not found |
| 409 | Conflict (pipeline already running) |
| 500 | Internal server error |
| 503 | Service unavailable (database down) |

### 3.4 API Router Registration

In `app/main.py`, routers are mounted with consistent prefixes:

```python
from app.routers import health, scraping, analysis, analytics, suggestions

app.include_router(health.router, tags=["Health"])
app.include_router(scraping.router, prefix="/api/v1/scraping", tags=["Scraping"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(suggestions.router, prefix="/api/v1/analytics", tags=["Suggestions"])
```

---

## 4. Data Flow

### 4.1 Full Pipeline Flow

```
[Trigger]
   |
   |  POST /api/v1/scraping/run   (manual)
   |  -- OR --
   |  APScheduler IntervalTrigger  (every 6h)
   |
   v
+------------------+
| Acquire Lock     |  threading.Lock -- prevents concurrent runs
| Create Run       |  INSERT scraping_runs (status=running)
+--------+---------+
         |
         v
+------------------+
| PHASE 1:         |
| Scrape Posts     |  For each candidate (2 total):
|                  |    apify-client -> instagram-post-scraper
|                  |    UPSERT posts (dedup on instagram_id)
|                  |    Update scraping_runs.posts_scraped
+--------+---------+
         |
         v
+------------------+
| PHASE 2:         |
| Scrape Comments  |  For each scraped post:
|                  |    apify-client -> instagram-comment-scraper
|                  |    UPSERT comments (dedup on instagram_id)
|                  |    Update scraping_runs.comments_scraped
+--------+---------+
         |
         v
+------------------+
| PHASE 3:         |
| VADER Analysis   |  For each unanalyzed comment:
|                  |    vaderSentiment -> compound score
|                  |    Classify: pos/neg/neutral
|                  |    INSERT sentiment_scores
+--------+---------+
         |
         v
+------------------+
| PHASE 4:         |
| LLM Fallback     |  For each ambiguous comment:
|                  |    (-0.05 < compound < 0.05) AND len(text) > 20
|                  |    httpx -> OpenAI GPT-4o-mini
|                  |    UPDATE sentiment_scores (llm_label, final_label)
+--------+---------+
         |
         v
+------------------+
| PHASE 5:         |
| Theme Extraction |  For each unclassified comment:
|                  |    Keyword matching against theme lists
|                  |    INSERT themes
+--------+---------+
         |
         v
+------------------+
| Complete Run     |  UPDATE scraping_runs (status=success, completed_at)
| Release Lock     |
+------------------+
```

### 4.2 Sentiment Analysis Decision Flow

```
Comment Text
     |
     v
+----------+
| VADER    |  vaderSentiment.polarity_scores(text)
| Analyze  |  -> compound score (float, -1.0 to 1.0)
+----+-----+
     |
     +-- compound >= 0.05  --> label = "positive"  --> final_label = "positive"
     |
     +-- compound <= -0.05 --> label = "negative"  --> final_label = "negative"
     |
     +-- otherwise (ambiguous zone):
          |
          +-- text length <= 20 chars --> final_label = "neutral" (skip LLM)
          |
          +-- text length > 20 chars --> LLM FALLBACK:
               |
               v
          +----------+
          | LLM API  |  Prompt in Portuguese, request pos/neg/neutral + confidence
          +----+-----+
               |
               +-- llm_confidence >= 0.7 --> final_label = llm_label
               |
               +-- llm_confidence < 0.7  --> final_label = "neutral" (VADER retained)
               |
               +-- API error            --> final_label = "neutral" (VADER retained)
```

### 4.3 Theme Extraction Flow

```
Comment Text
     |
     v
+-------------------+
| Keyword Matcher   |  Match against predefined theme keyword lists:
|                   |  - saude: ["saude", "hospital", "medico", "sus", "vacina", ...]
|                   |  - seguranca: ["seguranca", "policia", "violencia", "crime", ...]
|                   |  - educacao: ["educacao", "escola", "professor", "ensino", ...]
|                   |  - economia: ["economia", "emprego", "salario", "preco", ...]
|                   |  - infraestrutura: ["obra", "asfalto", "saneamento", "rua", ...]
|                   |  - corrupcao: ["corrupcao", "roubo", "desvio", "propina", ...]
|                   |  - emprego: ["emprego", "trabalho", "desemprego", "carteira", ...]
|                   |  - meio_ambiente: ["ambiente", "lixo", "poluicao", "verde", ...]
|                   |  - outros: (default, no keyword match)
+--------+----------+
         |
         v
  Match found?
     |
     +-- Yes --> INSERT themes (theme, confidence=1.0, method="keyword")
     |
     +-- No  --> INSERT themes (theme="outros", confidence=0.5, method="default")
```

### 4.4 Frontend Data Flow

```
User opens Dashboard Tab
         |
         v
    Page Component
         |
         v
  Custom Hook (e.g., useOverview)
         |
    fetch(NEXT_PUBLIC_API_URL + endpoint)
         |
    +----+----+--------+
    |         |        |
    v         v        v
  Loading   Error    Data
  (Skeleton) (Message) (Render)
         |
         v
  User interacts (filter, sort, date range)
         |
         v
  Hook re-fetches with new parameters
         |
         v
  UI re-renders
```

---

## 5. Database Schema

### 5.1 Entity Relationship Diagram

```
+-------------+       +-------------+       +-------------+
| candidates  |       |    posts    |       |  comments   |
+-------------+       +-------------+       +-------------+
| id (PK)     |<------| candidate_id|<------| post_id     |
| username     |  1:N  | id (PK)     |  1:N  | id (PK)     |
| display_name |       | instagram_id|       | instagram_id|
| created_at   |       | url         |       | text        |
+-------------+       | caption     |       | author_user |
                       | like_count  |       | like_count  |
                       | comment_cnt |       | commented_at|
                       | media_type  |       | scraped_at  |
                       | posted_at   |       +------+------+
                       | scraped_at  |              |
                       +-------------+              |
                                                    | 1:1
                                              +-----v--------+
                                              |sentiment_scores|
                                              +--------------+
                                              | id (PK)      |
                                              | comment_id(FK)|
                                              | vader_compound|
                                              | vader_label   |
                                              | llm_label     |
                                              | llm_confidence|
                                              | final_label   |
                                              | analyzed_at   |
                                              +--------------+
                                                    |
                                              +-----v------+
                                              |   themes   |  1:N
                                              +------------+
                                              | id (PK)    |
                                              | comment_id |
                                              | theme      |
                                              | confidence |
                                              | method     |
                                              +------------+

+----------------+
| scraping_runs  |  (independent, no FK relationships)
+----------------+
| id (PK)        |
| started_at     |
| completed_at   |
| status         |
| posts_scraped  |
| comments_scraped|
| errors (JSONB) |
+----------------+
```

### 5.2 SQL DDL (Migration 001)

```sql
-- 001_initial_schema.sql
-- Instagram Campaign Analytics - Initial Schema
-- PRD References: FR-005, CON-005, NFR-004

-- ===========================================
-- TABLE: candidates
-- ===========================================
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ===========================================
-- TABLE: posts
-- ===========================================
CREATE TABLE IF NOT EXISTS posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    instagram_id TEXT UNIQUE NOT NULL,
    url TEXT,
    caption TEXT,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    media_type TEXT,
    posted_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_posts_candidate_id ON posts(candidate_id);
CREATE INDEX idx_posts_posted_at ON posts(posted_at DESC);

-- ===========================================
-- TABLE: comments
-- ===========================================
CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    instagram_id TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    author_username TEXT,
    like_count INTEGER DEFAULT 0,
    commented_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_commented_at ON comments(commented_at DESC);

-- ===========================================
-- TABLE: sentiment_scores
-- ===========================================
CREATE TABLE IF NOT EXISTS sentiment_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID UNIQUE NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    vader_compound FLOAT,
    vader_label TEXT,
    llm_label TEXT,
    llm_confidence FLOAT,
    final_label TEXT NOT NULL,
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sentiment_comment_id ON sentiment_scores(comment_id);
CREATE INDEX idx_sentiment_final_label ON sentiment_scores(final_label);

-- ===========================================
-- TABLE: scraping_runs
-- ===========================================
CREATE TABLE IF NOT EXISTS scraping_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    posts_scraped INTEGER DEFAULT 0,
    comments_scraped INTEGER DEFAULT 0,
    errors JSONB
);

-- ===========================================
-- TABLE: themes
-- ===========================================
CREATE TABLE IF NOT EXISTS themes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    theme TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    method TEXT NOT NULL DEFAULT 'keyword'
);

CREATE INDEX idx_themes_theme ON themes(theme);
CREATE INDEX idx_themes_comment_id ON themes(comment_id);

-- ===========================================
-- SEED DATA: Monitored Candidates
-- ===========================================
INSERT INTO candidates (username, display_name) VALUES
    ('charlles.evangelista', 'Charlles Evangelista'),
    ('delegadasheila', 'Delegada Sheila')
ON CONFLICT (username) DO NOTHING;
```

### 5.3 Index Strategy

| Table | Index | Column(s) | Rationale |
|-------|-------|-----------|-----------|
| posts | idx_posts_candidate_id | candidate_id | Filter posts by candidate (every analytics query) |
| posts | idx_posts_posted_at | posted_at DESC | Timeline sorting, date range filtering |
| comments | idx_comments_post_id | post_id | Join comments to posts |
| comments | idx_comments_commented_at | commented_at DESC | Temporal queries on comments |
| sentiment_scores | idx_sentiment_comment_id | comment_id | Join sentiment to comments |
| sentiment_scores | idx_sentiment_final_label | final_label | Aggregate sentiment counts |
| themes | idx_themes_theme | theme | Group by theme aggregation |
| themes | idx_themes_comment_id | comment_id | Join themes to comments |

Performance note per NFR-004: With the expected data volume of 10,000 comments total (10 posts x 2 candidates x ~500 comments), these indexes ensure sub-second query execution for all analytics endpoints. No partitioning is needed at this scale.

---

## 6. Integration Points

### 6.1 Apify Integration

| Property | Value |
|----------|-------|
| SDK | `apify-client` v1.8.1 |
| Authentication | Bearer token via `APIFY_TOKEN` env var |
| Post Scraper | Actor: `apify/instagram-post-scraper` |
| Comment Scraper | Actor: `apify/instagram-comment-scraper` |
| Invocation | Synchronous (`actor.call()` waits for completion) |
| Cost control | Max 10 posts per candidate, 4 actor runs per cycle (NFR-009) |

**Post Scraper Input:**
```python
{
    "usernames": ["charlles.evangelista"],
    "resultsLimit": 10
}
```

**Comment Scraper Input:**
```python
{
    "directUrls": ["https://www.instagram.com/p/abc123/"],
    "resultsLimit": 500
}
```

**Error handling strategy (NFR-005):**
- Wrap each actor call in try/except
- Log failure with candidate username, actor name, and error details
- Continue with next candidate/post on failure (partial data preserved)
- Update `scraping_runs.errors` JSONB with failure context
- Retry on next scheduled cycle (no immediate retry)

### 6.2 Supabase Integration

| Property | Value |
|----------|-------|
| SDK | `supabase-py` v2.10.0 |
| Authentication | Service key via `SUPABASE_KEY` env var |
| Connection | HTTPS to Supabase project URL |
| Operations | CRUD via SDK methods (`.insert()`, `.upsert()`, `.select()`, `.update()`) |
| No ORM | Per CON-003, no SQLAlchemy or equivalent |

**Client initialization pattern (singleton):**

```python
# app/db/supabase.py
from supabase import create_client, Client
from app.core.config import settings

_client: Client | None = None

def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client
```

**Upsert pattern for deduplication:**

```python
# Upsert posts using instagram_id as conflict key
supabase.table("posts").upsert(
    post_data,
    on_conflict="instagram_id"
).execute()
```

### 6.3 LLM Integration (OpenAI)

| Property | Value |
|----------|-------|
| Client | `httpx` v0.27.0 (async) |
| Default Provider | OpenAI |
| Default Model | GPT-4o-mini |
| Configuration | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` env vars |
| Use Cases | (1) Fallback sentiment reclassification, (2) Strategic suggestions |

**Sentiment reclassification prompt structure:**

```python
{
    "model": settings.LLM_MODEL,  # "gpt-4o-mini"
    "messages": [
        {
            "role": "system",
            "content": "Voce e um analista de sentimento para comentarios em portugues do Instagram. Classifique o comentario como 'positive', 'negative' ou 'neutral'. Responda APENAS em JSON: {\"label\": \"positive|negative|neutral\", \"confidence\": 0.0-1.0}"
        },
        {
            "role": "user",
            "content": f"Classifique o sentimento: \"{comment_text}\""
        }
    ],
    "temperature": 0.1,
    "max_tokens": 50
}
```

**Strategic suggestions prompt structure:**

```python
{
    "model": settings.LLM_MODEL,
    "messages": [
        {
            "role": "system",
            "content": "Voce e um consultor estrategico de campanha politica. Analise os dados fornecidos e gere 3-5 sugestoes estrategicas acionaveis. Cada sugestao deve ter: titulo, descricao, dado de apoio especifico, e prioridade (high/medium/low). Responda em JSON."
        },
        {
            "role": "user",
            "content": f"Dados da campanha:\n{analytics_summary_json}"
        }
    ],
    "temperature": 0.7,
    "max_tokens": 1000
}
```

**Cost control measures (CON-009):**
- VADER processes all comments first (free, ~10ms per comment)
- LLM only invoked for ambiguous subset (~10-20% of comments)
- GPT-4o-mini pricing is lowest tier with acceptable Portuguese quality
- `temperature: 0.1` for sentiment (deterministic), `0.7` for suggestions (creative)
- Log API call counts per run for cost monitoring

### 6.4 Frontend <-> API Integration

| Property | Value |
|----------|-------|
| Protocol | HTTPS REST |
| Format | JSON |
| Auth | None (MVP) |
| CORS | Production: Vercel domain only; Dev: wildcard |
| Base URL | `NEXT_PUBLIC_API_URL` env var |
| Client | Native `fetch` API |

**API client pattern:**

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL;

export async function fetchOverview(): Promise<OverviewData> {
  const res = await fetch(`${API_BASE}/api/v1/analytics/overview`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

---

## 7. Security Considerations

### 7.1 Threat Model (MVP)

| Threat | Risk Level | Mitigation | PRD Reference |
|--------|-----------|------------|---------------|
| API key exposure in source code | HIGH | All secrets in env vars, `.env` in `.gitignore` | NFR-006 |
| API key exposure in logs | MEDIUM | Structured logging masks sensitive fields | NFR-006, NFR-008 |
| Unauthorized API access | LOW (internal tool) | CORS lockdown to frontend domain | NFR-006 |
| Apify token theft | MEDIUM | Token rotation capability, minimal permissions | NFR-006 |
| SQL injection | LOW | Supabase SDK parameterizes all queries | CON-003 |
| CORS bypass | LOW | Strict origin validation in production | NFR-006 |
| LLM prompt injection | LOW | Fixed system prompts, no user-generated prompt content | -- |
| Data scraping legality | MEDIUM | Uses public data via Apify (not private APIs) | CON-001 |

### 7.2 CORS Configuration

**Development:**
```python
allow_origins=["*"]  # Wide open for local development
```

**Production:**
```python
# app/main.py
import os

allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

**ALLOWED_ORIGINS value in Railway:**
```
https://instagram-campaign-web.vercel.app
```

### 7.3 Secret Management

| Secret | Environment Variable | Where Stored |
|--------|---------------------|-------------|
| Supabase URL | `SUPABASE_URL` | Railway env vars |
| Supabase service key | `SUPABASE_KEY` | Railway env vars |
| Apify token | `APIFY_TOKEN` | Railway env vars |
| LLM provider | `LLM_PROVIDER` | Railway env vars |
| LLM model | `LLM_MODEL` | Railway env vars |
| LLM API key | `LLM_API_KEY` | Railway env vars |
| Allowed origins | `ALLOWED_ORIGINS` | Railway env vars |
| Log level | `LOG_LEVEL` | Railway env vars |
| Scraping interval | `SCRAPING_INTERVAL_HOURS` | Railway env vars |
| API base URL | `NEXT_PUBLIC_API_URL` | Vercel env vars |

**Important:** `NEXT_PUBLIC_API_URL` is the only secret on the frontend, and it is a public URL (not sensitive). No other secrets exist in the frontend build.

### 7.4 Rate Limiting Strategy

No custom rate limiting is implemented for MVP (internal tool with 3 known users). If needed in the future, the recommended approach is:

1. Add `slowapi` to requirements
2. Apply rate limits to scraping trigger endpoints (prevent accidental rapid-fire)
3. Suggested limit: 1 req/min for `POST /api/v1/scraping/run`

---

## 8. Deployment Architecture

### 8.1 Deployment Diagram

```
                      INTERNET
                         |
            +------------+------------+
            |                         |
            v                         v
    +-------+--------+      +--------+--------+
    |    Vercel CDN   |      | Railway Platform |
    |  (Edge Network) |      |  (Docker Host)   |
    +-------+--------+      +--------+--------+
            |                         |
            v                         v
    +-------+--------+      +--------+--------+
    | Next.js 16 App |      | Docker Container |
    |                |      |                  |
    | Static + SSR   | ---->| FastAPI App      |
    | pages          | REST | + APScheduler    |
    |                |      | + Uvicorn        |
    | Env:           |      |                  |
    | NEXT_PUBLIC_   |      | Env:             |
    |   API_URL      |      | SUPABASE_URL     |
    +----------------+      | SUPABASE_KEY     |
                            | APIFY_TOKEN      |
                            | LLM_API_KEY      |
                            | ALLOWED_ORIGINS  |
                            +--------+---------+
                                     |
                      +--------------+--------------+
                      |              |              |
                      v              v              v
              +-------+--+   +------+---+   +------+---+
              | Supabase  |   | Apify    |   | OpenAI   |
              | PostgreSQL|   | Cloud    |   | API      |
              |           |   |          |   |          |
              | Tables:   |   | Actors:  |   | Model:   |
              | candidates|   | post-    |   | gpt-4o-  |
              | posts     |   | scraper  |   | mini     |
              | comments  |   | comment- |   |          |
              | sentiment |   | scraper  |   |          |
              | themes    |   |          |   |          |
              | runs      |   |          |   |          |
              +-----------+   +----------+   +----------+
```

### 8.2 Docker Configuration (Production)

```dockerfile
# Dockerfile (optimized for production)
# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Security: non-root user
RUN useradd --create-home appuser
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: The current `Dockerfile` uses `python:3.12-slim` without multi-stage build. The production version above uses `python:3.11-slim` per CON-003 and adds multi-stage build, non-root user, and health check per Story 3.1 acceptance criteria.

### 8.3 Railway Configuration

```toml
# railway.toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 10
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### 8.4 Environment Variable Summary

**Railway (API):**

| Variable | Example Value | Required |
|----------|--------------|----------|
| `SUPABASE_URL` | `https://xxx.supabase.co` | Yes |
| `SUPABASE_KEY` | `eyJ...` (service_role key) | Yes |
| `APIFY_TOKEN` | `apify_api_xxx` | Yes |
| `LLM_PROVIDER` | `openai` | Yes |
| `LLM_MODEL` | `gpt-4o-mini` | Yes |
| `LLM_API_KEY` | `sk-xxx` | Yes |
| `ALLOWED_ORIGINS` | `https://instagram-campaign-web.vercel.app` | Yes |
| `SCRAPING_INTERVAL_HOURS` | `6` | No (default: 6) |
| `LOG_LEVEL` | `INFO` | No (default: INFO) |
| `PORT` | (injected by Railway) | Auto |

**Vercel (Frontend):**

| Variable | Example Value | Required |
|----------|--------------|----------|
| `NEXT_PUBLIC_API_URL` | `https://instagram-campaign-api-production.up.railway.app` | Yes |

---

## 9. Technology Decisions

### 9.1 Sentiment Analysis: VADER + LLM Fallback

**Decision:** Use VADER as primary analyzer, GPT-4o-mini as fallback for ambiguous cases.

**Alternatives considered:**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| VADER only | Free, fast (~1ms/comment), no API dependency | Poor Portuguese accuracy, no nuance | Insufficient alone |
| TextBlob | Simple API, better than VADER for some cases | No Portuguese support, similar accuracy issues | Worse than VADER |
| Fine-tuned BERT (pt-br) | High accuracy for Portuguese | Requires training data, GPU inference, complex setup, high cost | Overkill for MVP |
| LLM only (GPT-4) | Best accuracy, native Portuguese | ~$0.01/comment, 500ms latency per call, 10K comments = $100/cycle | Too expensive |
| **VADER + LLM fallback** | **Free for ~85% of comments, high accuracy for remaining 15%** | **Hybrid complexity** | **Selected** |

**Rationale:** The two-tier approach (PRD FR-003 + FR-004) uses VADER to handle the ~85% of comments that produce confident scores (above or below the 0.05 threshold), costing nothing and completing in milliseconds. Only the ambiguous 15% reach the LLM at ~$0.001/comment (GPT-4o-mini), keeping costs under $2/month for 10K comments. This respects CON-009 (budget) while achieving acceptable Portuguese accuracy per NFR-003.

### 9.2 Charting: Recharts

**Decision:** Use Recharts as the sole charting library.

**Alternatives considered:**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| D3.js | Maximum flexibility, any visualization possible | Steep learning curve, verbose, no React integration | Overkill |
| Chart.js + react-chartjs-2 | Simple, lightweight, good defaults | Less React-native, limited customization | Good but not best |
| **Recharts** | **React-native, declarative, good defaults, responsive** | **Fewer chart types than D3** | **Selected** |
| Victory | React-native, animation support | Heavier bundle, smaller community | Too heavy |
| Tremor | Beautiful defaults, Tailwind-native | Less customization, opinionated | Limited |

**Rationale:** Per CON-004, Recharts is the mandated charting library. It integrates naturally with React's component model, supports `ResponsiveContainer` for adaptive layouts, and covers all required chart types (Line, Bar, Pie) with minimal configuration. For the word cloud (FR-008), a dedicated library (`react-wordcloud` or `@visx/wordcloud`) supplements Recharts since word clouds are not a standard chart type.

### 9.3 Web Framework: FastAPI

**Decision:** FastAPI as the backend framework. Not a choice point (per CON-003), but the rationale is documented.

| Property | FastAPI | Flask | Django REST |
|----------|---------|-------|-------------|
| Async support | Native | Extension | Extension |
| Auto-docs | Built-in (OpenAPI) | Manual | Built-in |
| Pydantic integration | Native | Manual | Serializers |
| Performance | Top tier (Starlette) | Moderate | Moderate |
| Learning curve | Low | Low | Medium |
| Type safety | Excellent | Minimal | Good |

**Rationale:** FastAPI provides automatic request/response validation through Pydantic (NFR-010), built-in OpenAPI documentation at `/docs`, native async support for httpx LLM calls, and excellent developer experience. The auto-generated Swagger UI eliminates the need for separate API documentation effort.

### 9.4 Scheduling: APScheduler In-Process

**Decision:** APScheduler `BackgroundScheduler` running inside the FastAPI process.

**Alternatives considered:**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Celery + Redis | Robust, distributed, retry logic | Requires Redis, complex setup, overkill for 2 candidates | Too heavy |
| Railway Cron Jobs | Managed, no in-process state | Cold start latency, separate config, limited control | Good but less control |
| **APScheduler in-process** | **Simple, no external deps, good enough for single-process** | **Lost on restart, single-process only** | **Selected** |
| OS cron + HTTP trigger | Simple, reliable | External to application, harder to monitor | Fragile |

**Rationale:** Per PRD 12.4, APScheduler runs in-process with FastAPI. This is the simplest approach for a single-process deployment on Railway. The `threading.Lock` prevents concurrent pipeline runs. If the service restarts, the scheduler reinitializes and resumes on the configured interval -- no state is lost since all data is in Supabase.

### 9.5 Database: Supabase PostgreSQL (No ORM)

**Decision:** Use `supabase-py` SDK directly, no ORM layer.

**Rationale:** Per CON-003, the project uses the Supabase Python client directly. This avoids the overhead of ORM mapping for a relatively simple schema (6 tables). The Supabase SDK provides `.insert()`, `.upsert()`, `.select()`, `.update()` methods that map cleanly to the CRUD operations needed. Pydantic models handle data validation at the application layer, making an ORM redundant.

**Trade-off:** Without an ORM, complex joins require manual query construction. For this project's analytics queries, Supabase's `.select("*, posts!inner(*)")` syntax and server-side functions handle the needed joins adequately.

### 9.6 Frontend: Next.js 16 with App Router

**Decision:** Next.js 16 with App Router, Tailwind CSS, shadcn/ui.

**Rationale:** Per CON-004, this is the mandated frontend stack. Key architectural benefits:
- **App Router** provides file-based routing that maps cleanly to the 7 dashboard views
- **Server Components** can be used for the layout shell (static header/nav)
- **Client Components** for interactive views (charts, filters, data fetching)
- **shadcn/ui** provides accessible, customizable components without the bundle cost of a full component library
- **Tailwind CSS** enables rapid styling with utility classes, consistent spacing/colors

---

## 10. Non-Functional Requirements Mapping

| NFR | Architecture Response |
|-----|----------------------|
| NFR-001 (Response Time < 2s) | PostgreSQL indexes on all query columns; Supabase SDK executes optimized queries; no N+1 patterns in service layer |
| NFR-002 (Data Freshness < 7h) | APScheduler with 6h interval; health endpoint reports last scrape timestamp |
| NFR-003 (Portuguese Support) | VADER baseline + LLM fallback with Portuguese prompts; Portuguese stop words list for word cloud |
| NFR-004 (10K comments scale) | Indexes on all join/filter columns; batch processing in sentiment analysis; sequential Apify calls |
| NFR-005 (Error Resilience) | Try/except around each Apify call; partial data preservation; error logging in scraping_runs |
| NFR-006 (Security) | Env vars for all secrets; CORS lockdown; no token logging |
| NFR-007 (Deployment) | Docker + Railway (API); Vercel (FE); env var injection on both platforms |
| NFR-008 (Observability) | Structured logging with `logging` module; scraping_runs table as audit trail |
| NFR-009 (Cost Efficiency) | Max 4 Apify runs/cycle; VADER-first sentiment; GPT-4o-mini for fallback |
| NFR-010 (Code Quality) | Pydantic models for all schemas; type hints on all functions; PEP 8 compliance |

---

## 11. Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0.0 | Initial architecture document | Aria (Architect Agent) |

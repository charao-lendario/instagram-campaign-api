# Epic 1: Backend (FastAPI + Apify)

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-1 |
| **Title** | Backend API -- Scraping, Sentiment Analysis & Data Pipeline |
| **Status** | Draft |
| **Repository** | instagram-campaign-api |
| **Stories** | 7 |
| **PRD Reference** | `docs/prd/PRD-instagram-campaign.md` |

---

## Goal

Build the complete backend API that scrapes Instagram data for both monitored candidates (@charlles.evangelista, @delegadasheila), performs sentiment analysis on every comment, extracts recurring themes, persists all data to Supabase PostgreSQL, and exposes RESTful endpoints that serve every view the frontend dashboard needs. By the end of this epic, the API is fully functional and testable via HTTP client -- no frontend dependency.

---

## Scope

### In Scope
- Supabase PostgreSQL schema (candidates, posts, comments, sentiment_scores, themes, scraping_runs)
- Apify integration for post scraping (instagram-post-scraper) and comment scraping (instagram-comment-scraper)
- VADER sentiment analysis with score storage
- LLM fallback sentiment analysis for ambiguous comments
- Analytics endpoints (overview metrics, temporal sentiment, themes, post ranking, candidate comparison)
- APScheduler for periodic automated scraping
- LLM-powered strategic suggestions endpoint
- Manual scraping trigger endpoint
- Health check endpoint with database and last-scrape status
- Structured logging for all scraping operations

### Out of Scope
- Frontend implementation (Epic 2)
- Deployment to Railway (Epic 3)
- User authentication
- WebSocket real-time updates
- Comment reply threading

---

## Dependencies

- Supabase project created with PostgreSQL database accessible
- Apify account with API token and access to instagram-post-scraper and instagram-comment-scraper actors
- LLM API key (OpenAI or configurable provider)

---

## Stories

---

### Story 1.1: Database Schema & Supabase Setup

**As a** backend developer,
**I want** a well-structured PostgreSQL schema in Supabase with all required tables and indexes,
**so that** all subsequent stories have a reliable data layer to build upon.

**PRD References**: FR-005, CON-005, NFR-004

#### Acceptance Criteria

1. Supabase project connection is configured via environment variables (SUPABASE_URL, SUPABASE_KEY) loaded through pydantic-settings.
2. The following tables exist in Supabase with correct data types and constraints:
   - `candidates` (id UUID PK, username TEXT UNIQUE NOT NULL, display_name TEXT, created_at TIMESTAMPTZ DEFAULT NOW())
   - `posts` (id UUID PK, candidate_id UUID FK -> candidates, instagram_id TEXT UNIQUE NOT NULL, url TEXT, caption TEXT, like_count INT, comment_count INT, media_type TEXT, posted_at TIMESTAMPTZ, scraped_at TIMESTAMPTZ DEFAULT NOW())
   - `comments` (id UUID PK, post_id UUID FK -> posts, instagram_id TEXT UNIQUE NOT NULL, text TEXT NOT NULL, author_username TEXT, like_count INT, commented_at TIMESTAMPTZ, scraped_at TIMESTAMPTZ DEFAULT NOW())
   - `sentiment_scores` (id UUID PK, comment_id UUID FK -> comments UNIQUE, vader_compound FLOAT, vader_label TEXT, llm_label TEXT NULLABLE, llm_confidence FLOAT NULLABLE, final_label TEXT NOT NULL, analyzed_at TIMESTAMPTZ DEFAULT NOW())
   - `scraping_runs` (id UUID PK, started_at TIMESTAMPTZ DEFAULT NOW(), completed_at TIMESTAMPTZ NULLABLE, status TEXT NOT NULL, posts_scraped INT DEFAULT 0, comments_scraped INT DEFAULT 0, errors JSONB NULLABLE)
   - `themes` (id UUID PK, comment_id UUID FK -> comments, theme TEXT NOT NULL, confidence FLOAT, method TEXT NOT NULL)
3. Indexes are created on: `posts.candidate_id`, `posts.posted_at`, `comments.post_id`, `comments.commented_at`, `sentiment_scores.comment_id`, `sentiment_scores.final_label`, `themes.theme`.
4. Seed data inserts the two monitored candidates: @charlles.evangelista and @delegadasheila.
5. A Supabase client module (`app/db/supabase.py`) provides a configured client instance usable by all services.
6. SQL migration file(s) are stored in `docs/architecture/migrations/` for reproducibility.
7. Unit tests verify the Supabase client initialization and seed data existence.

#### Dev Notes
- Use `supabase-py` client, not raw SQL connections.
- Pydantic models for all table entities go in `app/models/`.
- Environment config via `app/core/config.py` using pydantic-settings.

---

### Story 1.2: Apify Post Scraping Service

**As a** campaign analyst,
**I want** the system to automatically scrape the latest 10 posts from each monitored candidate's Instagram profile,
**so that** I have fresh post data to analyze engagement patterns.

**PRD References**: FR-001, CON-001, CON-002, NFR-005, NFR-009

#### Acceptance Criteria

1. A service module `app/services/scraping.py` implements a `scrape_posts(candidate_username: str) -> list[Post]` function.
2. The service uses `apify-client` to call the `instagram-post-scraper` actor with the candidate username and a limit of 10 posts.
3. Each scraped post is mapped to the `Post` Pydantic model and upserted into the `posts` table (using `instagram_id` as the deduplication key).
4. The function returns the list of upserted posts with their database IDs.
5. If the Apify actor run fails, the function raises a descriptive exception and does not crash the application. The error is logged with structured logging (candidate, actor, error message).
6. A `scraping_runs` record is created at the start of each scraping operation and updated upon completion (status: success/failed, posts_scraped count).
7. An API endpoint `POST /api/v1/scraping/posts` triggers post scraping for all monitored candidates and returns the run status.
8. Unit tests mock the Apify client and verify: successful scraping, deduplication, and error handling.

#### Dev Notes
- Apify token via environment variable `APIFY_TOKEN`.
- Actor ID for instagram-post-scraper should be configurable in settings.

---

### Story 1.3: Apify Comment Scraping Service

**As a** campaign analyst,
**I want** all comments from each scraped post to be collected,
**so that** sentiment analysis and theme extraction have complete data to work with.

**PRD References**: FR-002, CON-001, NFR-005, NFR-009

#### Acceptance Criteria

1. A function `scrape_comments(post_url: str, post_id: UUID) -> list[Comment]` is added to `app/services/scraping.py`.
2. The function uses `apify-client` to call the `instagram-comment-scraper` actor for the given post URL.
3. Each scraped comment is mapped to the `Comment` Pydantic model and upserted into the `comments` table (using `instagram_id` as deduplication key).
4. A higher-level function `scrape_all_comments(posts: list[Post]) -> int` iterates through posts and scrapes comments for each, returning total comments scraped.
5. Failed individual post comment scraping does not halt the overall process -- errors are logged and the function continues with remaining posts.
6. The `scraping_runs` record is updated with `comments_scraped` count and any errors appended to the `errors` JSONB field.
7. An API endpoint `POST /api/v1/scraping/comments` triggers comment scraping for all posts that have been scraped but not yet had comments collected (or whose comments are older than the configured staleness threshold).
8. Unit tests mock the Apify client and verify: successful comment scraping, deduplication, partial failure handling.

#### Dev Notes
- Consider batching: scrape comments for multiple posts sequentially to avoid Apify concurrency limits.
- Depends on Story 1.2 (posts must exist before comments can be scraped).

---

### Story 1.4: VADER Sentiment Analysis

**As a** campaign strategist,
**I want** every comment to be automatically classified as positive, negative, or neutral,
**so that** I can quantify public sentiment toward each candidate.

**PRD References**: FR-003, NFR-003, NFR-004

#### Acceptance Criteria

1. A service module `app/services/sentiment.py` implements `analyze_sentiment_vader(comment_text: str) -> SentimentResult` returning compound score and label.
2. Classification thresholds: compound >= 0.05 = "positive", compound <= -0.05 = "negative", otherwise "neutral".
3. A batch function `analyze_comments_batch(comments: list[Comment]) -> list[SentimentScore]` processes all unanalyzed comments and creates `sentiment_scores` records.
4. The `vader_compound`, `vader_label`, and `final_label` fields are populated. `llm_label` and `llm_confidence` remain NULL (handled in Story 1.5).
5. Duplicate analysis is prevented -- comments that already have a `sentiment_scores` record are skipped.
6. An API endpoint `POST /api/v1/analysis/sentiment` triggers sentiment analysis for all unanalyzed comments and returns the count of newly analyzed comments.
7. An API endpoint `GET /api/v1/analysis/sentiment/summary?candidate_id={id}` returns aggregate sentiment counts (positive, negative, neutral) and average compound score for a given candidate.
8. Unit tests verify: correct classification at boundary values (0.05, -0.05, 0.0), batch processing, and deduplication.

#### Dev Notes
- `vaderSentiment` is English-optimized. Portuguese accuracy is limited but acceptable as baseline per NFR-003.
- This story establishes the baseline; Story 1.5 adds LLM fallback.

---

### Story 1.5: LLM Fallback Sentiment Analysis

**As a** campaign strategist,
**I want** ambiguous comments to be reclassified by an LLM for better accuracy,
**so that** sentiment data reflects Portuguese-language nuance that VADER may miss.

**PRD References**: FR-004, NFR-003, CON-008, CON-009

#### Acceptance Criteria

1. A function `analyze_sentiment_llm(comment_text: str) -> LLMSentimentResult` is added to `app/services/sentiment.py`.
2. The function calls the configured LLM API (provider, model, and API key via environment variables) with a Portuguese-language prompt instructing classification as positive/negative/neutral with a confidence score (0.0-1.0).
3. A function `reclassify_ambiguous_comments()` selects all comments where VADER compound is in the range (-0.05 < score < 0.05) AND text length > 20 characters, and submits them to the LLM for reclassification.
4. The `sentiment_scores` record is updated: `llm_label`, `llm_confidence` are populated. `final_label` is updated to the LLM label when `llm_confidence >= 0.7`, otherwise retains the VADER label.
5. LLM API failures for individual comments are logged and do not halt batch processing. The VADER label is retained as `final_label` on failure.
6. An API endpoint `POST /api/v1/analysis/sentiment/llm-fallback` triggers LLM reclassification for all eligible ambiguous comments.
7. LLM costs are controlled: the function logs the number of API calls made per run.
8. Unit tests mock the LLM HTTP call and verify: successful reclassification, confidence threshold logic, error handling.

#### Dev Notes
- Use `httpx` async client for LLM API calls.
- Default LLM: OpenAI GPT-4o-mini (cheapest option with good Portuguese support).
- Depends on Story 1.4 (VADER analysis must run first).

---

### Story 1.6: Analytics & Comparison Endpoints

**As a** campaign strategist,
**I want** API endpoints that aggregate and compare engagement and sentiment data across candidates and posts,
**so that** the frontend dashboard can render all required visualizations.

**PRD References**: FR-006, FR-007, FR-009, FR-010, FR-011, NFR-001

#### Acceptance Criteria

1. `GET /api/v1/analytics/overview` returns for each candidate: total posts, total comments, average sentiment score, sentiment distribution (positive/negative/neutral counts), total engagement (sum of post likes + comment counts).
2. `GET /api/v1/analytics/sentiment-timeline?candidate_id={id}&start_date={date}&end_date={date}` returns a list of data points: post timestamp, average sentiment score for that post, post URL. Supports optional date range filtering.
3. `GET /api/v1/analytics/wordcloud?candidate_id={id}` returns word frequency data: list of {word, count} pairs, excluding Portuguese stop words. Stop words list is configurable.
4. `GET /api/v1/analytics/themes?candidate_id={id}` returns theme distribution: list of {theme, count, percentage} per candidate.
5. `GET /api/v1/analytics/posts?candidate_id={id}&sort_by={metric}&order={asc|desc}` returns a ranked list of posts with: URL, caption (truncated), like count, comment count, positive ratio, negative ratio. Supports sorting by any metric.
6. `GET /api/v1/analytics/comparison` returns side-by-side metrics for both candidates: all overview metrics plus top 3 themes, sentiment trend direction (improving/declining based on last 5 posts vs previous 5).
7. A theme extraction service `app/services/themes.py` classifies comments into predefined themes (saude, seguranca, educacao, economia, infraestrutura, corrupcao, emprego, meio_ambiente, outros) using keyword matching with configurable keyword lists.
8. All endpoints respond within 2 seconds per NFR-001. Database queries use the indexes created in Story 1.1.
9. All response models are defined as Pydantic schemas in `app/models/`.
10. Unit tests verify each endpoint returns correct data structure and handles empty data gracefully.

#### Dev Notes
- Portuguese stop words list: use a standard list (e.g., NLTK Portuguese stop words or a curated set in `app/core/constants.py`).
- Theme keywords should be stored in a configuration file or constants module for easy updates.
- Depends on Stories 1.1-1.5 (data must exist).

---

### Story 1.7: Scheduler & Strategic Suggestions

**As a** campaign coordinator,
**I want** scraping to run automatically on a schedule and the system to generate AI-powered strategic suggestions,
**so that** data is always fresh and the team receives actionable insights without manual intervention.

**PRD References**: FR-012, FR-013, FR-014, FR-015, NFR-002, NFR-005, NFR-008

#### Acceptance Criteria

1. APScheduler is integrated with FastAPI via a lifespan event. The scheduler starts on application startup and shuts down gracefully on application stop.
2. A scheduled job `run_full_pipeline()` executes the complete pipeline: scrape posts -> scrape comments -> VADER sentiment analysis -> LLM fallback -> theme extraction. The interval is configurable via `SCRAPING_INTERVAL_HOURS` environment variable (default: 6).
3. A concurrency lock prevents multiple pipeline runs from executing simultaneously. If a run is already in progress, the scheduled trigger is skipped with a warning log.
4. `POST /api/v1/scraping/run` triggers an immediate full pipeline run (manual trigger per FR-014). Returns 409 Conflict if a run is already in progress.
5. `GET /api/v1/health` returns: service status, database connectivity (can query Supabase), last successful scraping run timestamp, and scheduler status (running/stopped).
6. `POST /api/v1/analytics/suggestions` accepts an optional candidate_id parameter and returns 3-5 AI-generated strategic suggestions. Each suggestion includes: title, description, supporting data point (specific metric or comparison), and priority level (high/medium/low).
7. Strategic suggestions are generated by sending a structured prompt to the LLM with the current analytics summary (overview metrics, top themes, sentiment trends for both candidates).
8. All scheduler operations are logged with structured logging: run start, run completion, duration, records processed, errors.
9. Unit tests verify: scheduler initialization, concurrent run prevention, health check response, and suggestion generation (mocked LLM).

#### Dev Notes
- APScheduler `BackgroundScheduler` with `IntervalTrigger`.
- Use `threading.Lock` for concurrency prevention (single-process deployment).
- The full pipeline function should call services from Stories 1.2-1.5 in sequence.
- Depends on all previous stories (1.1-1.6).

---

## Definition of Done (Epic Level)

- [ ] All 7 stories implemented and passing unit tests.
- [ ] All API endpoints documented (FastAPI auto-docs at `/docs`).
- [ ] Health check returns healthy with database connectivity.
- [ ] A full pipeline run (scrape -> analyze -> serve) completes successfully against live Apify/Supabase.
- [ ] Structured logging operational for all scraping operations.
- [ ] Code follows PEP 8, all functions have type hints, all request/response schemas use Pydantic.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0.0 | Initial epic creation | Bob (PM Agent) |

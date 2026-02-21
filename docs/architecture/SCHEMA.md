# Database Schema - Instagram Campaign Analytics

| Field | Value |
|-------|-------|
| **Database** | Supabase PostgreSQL |
| **Version** | 1.0.0 |
| **Created** | 2026-02-21 |
| **PRD Reference** | `docs/prd/PRD-instagram-campaign.md` |
| **Migrations** | `supabase/migrations/001-005` |

---

## 1. Entity Relationship Diagram (ASCII)

```
+------------------+       +------------------+       +--------------------+
|   candidates     |       |  scraping_runs   |       | strategic_insights |
+------------------+       +------------------+       +--------------------+
| id (PK)          |       | id (PK)          |       | id (PK)            |
| username (UQ)    |       | started_at       |       | scraping_run_id FK |---+
| display_name     |       | completed_at     |       | candidate_id FK    |-+ |
| profile_url      |       | status           |       | title              | | |
| is_active        |       | posts_scraped    |       | description        | | |
| created_at       |       | comments_scraped |       | supporting_data    | | |
| updated_at       |       | duration_seconds |       | priority           | | |
+--------+---------+       | errors (JSONB)   |       | llm_model          | | |
         |                  | metadata (JSONB) |       | input_summary      | | |
         | 1                +--------+---------+       | created_at         | | |
         |                           |                  +--------------------+ | |
         |                           | 1                                      | |
         | N                         |                                        | |
+--------+---------+                 |                                        | |
|     posts        +-----------------+                                        | |
+------------------+  scraping_run_id (FK)                                    | |
| id (PK)          |                                                          | |
| candidate_id FK  |<--------------------------------------------------------+ |
| scraping_run_id  |<----------------------------------------------------------+
| instagram_id (UQ)|
| url              |
| shortcode        |
| caption          |
| like_count       |
| comment_count    |
| media_type       |
| is_sponsored     |
| video_view_count |
| posted_at        |
| scraped_at       |
| raw_data (JSONB) |
| created_at       |
| updated_at       |
+--------+---------+
         |
         | 1
         |
         | N
+--------+---------+
|    comments      |
+------------------+
| id (PK)          |
| post_id FK       |
| scraping_run_id  |
| instagram_id (UQ)|
| text             |
| author_username  |
| like_count       |
| reply_count      |
| commented_at     |
| scraped_at       |
| raw_data (JSONB) |
| created_at       |
+--------+---------+
         |
         | 1
         |
    +----+----+
    |         |
    | N       | 1
+---+------+  +------------------+
|  themes  |  | sentiment_scores |
+----------+  +------------------+
| id (PK)  |  | id (PK)          |
| comment_id|  | comment_id (UQ)  |
| theme     |  | vader_compound   |
| confidence|  | vader_positive   |
| method    |  | vader_negative   |
| created_at|  | vader_neutral    |
+----------+  | vader_label      |
               | llm_label        |
               | llm_confidence   |
               | llm_model        |
               | final_label      |
               | analyzed_at      |
               | created_at       |
               | updated_at       |
               +------------------+
```

### Relationships Summary

| Relationship | Type | FK Column | On Delete |
|-------------|------|-----------|-----------|
| candidates -> posts | 1:N | posts.candidate_id | CASCADE |
| posts -> comments | 1:N | comments.post_id | CASCADE |
| comments -> sentiment_scores | 1:1 | sentiment_scores.comment_id (UQ) | CASCADE |
| comments -> themes | 1:N | themes.comment_id | CASCADE |
| scraping_runs -> posts | 1:N | posts.scraping_run_id | SET NULL |
| scraping_runs -> comments | 1:N | comments.scraping_run_id | SET NULL |
| scraping_runs -> strategic_insights | 1:N | strategic_insights.scraping_run_id | SET NULL |
| candidates -> strategic_insights | 1:N | strategic_insights.candidate_id | SET NULL |

---

## 2. Custom Types (Enums)

### sentiment_label
Classification output for sentiment analysis.

| Value | Description | VADER Rule |
|-------|-------------|------------|
| `positive` | Positive sentiment | compound >= 0.05 |
| `negative` | Negative sentiment | compound <= -0.05 |
| `neutral` | Neutral/ambiguous | -0.05 < compound < 0.05 |

### scraping_status
Lifecycle status of a scraping run.

| Value | Description |
|-------|-------------|
| `running` | Scraping is currently in progress |
| `success` | All scraping completed without errors |
| `failed` | Scraping terminated due to errors |
| `partial` | Some candidates/posts succeeded, others failed |

### theme_category
Predefined thematic categories (PT-BR political context).

| Value | Display Name (PT-BR) |
|-------|---------------------|
| `saude` | Saude |
| `seguranca` | Seguranca |
| `educacao` | Educacao |
| `economia` | Economia |
| `infraestrutura` | Infraestrutura |
| `corrupcao` | Corrupcao |
| `emprego` | Emprego |
| `meio_ambiente` | Meio Ambiente |
| `outros` | Outros |

### analysis_method
Method used for classification.

| Value | Description |
|-------|-------------|
| `keyword` | Keyword-based matching (deterministic) |
| `llm` | LLM-based classification (probabilistic) |

### media_type
Instagram post media type.

| Value | Description |
|-------|-------------|
| `image` | Single image post |
| `video` | Video/Reel post |
| `carousel` | Multi-image carousel |
| `unknown` | Type could not be determined |

---

## 3. Table Definitions

### 3.1 candidates

Monitored Instagram candidate profiles. MVP: exactly 2.

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| username | TEXT | NOT NULL | - | UNIQUE | Instagram username (no @ prefix) |
| display_name | TEXT | NULL | - | - | Human-readable name |
| profile_url | TEXT | NOT NULL | GENERATED | STORED | Auto-generated: `https://instagram.com/{username}/` |
| is_active | BOOLEAN | NOT NULL | TRUE | - | Whether candidate is actively scraped |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | trigger | Auto-updated on modification |

### 3.2 scraping_runs

Audit log of scraping pipeline executions.

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| started_at | TIMESTAMPTZ | NOT NULL | NOW() | - | When the run started |
| completed_at | TIMESTAMPTZ | NULL | - | - | When the run finished (NULL if running) |
| status | scraping_status | NOT NULL | 'running' | - | Current status |
| posts_scraped | INTEGER | NOT NULL | 0 | - | Count of posts scraped this run |
| comments_scraped | INTEGER | NOT NULL | 0 | - | Count of comments scraped this run |
| duration_seconds | NUMERIC(10,2) | NULL | - | - | Wall-clock duration |
| errors | JSONB | NULL | - | - | Error details array |
| metadata | JSONB | NULL | - | - | Run configuration metadata |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |

**errors JSONB schema:**
```json
[
  {
    "candidate": "charlles.evangelista",
    "phase": "post_scraping",
    "message": "Apify actor timeout after 60s",
    "timestamp": "2026-02-21T10:00:00Z"
  }
]
```

### 3.3 posts

Instagram posts scraped from candidate profiles.

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| candidate_id | UUID | NOT NULL | - | FK -> candidates | Owning candidate |
| scraping_run_id | UUID | NULL | - | FK -> scraping_runs | Run that scraped this post |
| instagram_id | TEXT | NOT NULL | - | UNIQUE | Instagram post ID (dedup key) |
| url | TEXT | NOT NULL | - | - | Full post URL |
| shortcode | TEXT | NULL | - | - | Instagram shortcode from URL |
| caption | TEXT | NULL | - | - | Post caption text |
| like_count | INTEGER | NOT NULL | 0 | - | Number of likes |
| comment_count | INTEGER | NOT NULL | 0 | - | Number of comments |
| media_type | media_type | NOT NULL | 'unknown' | - | Image/video/carousel |
| is_sponsored | BOOLEAN | NOT NULL | FALSE | - | Whether post is sponsored |
| video_view_count | INTEGER | NULL | - | - | Video views (NULL for images) |
| posted_at | TIMESTAMPTZ | NULL | - | - | When posted on Instagram |
| scraped_at | TIMESTAMPTZ | NOT NULL | NOW() | - | When scraped by our system |
| raw_data | JSONB | NULL | - | - | Complete Apify response |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | trigger | Auto-updated on modification |

**Apify field mapping (instagram-post-scraper):**

| Apify Field | Database Column |
|-------------|----------------|
| `id` | instagram_id |
| `url` / `postUrl` | url |
| `shortCode` | shortcode |
| `caption` | caption |
| `likesCount` | like_count |
| `commentsCount` | comment_count |
| `type` | media_type |
| `isSponsored` | is_sponsored |
| `videoViewCount` | video_view_count |
| `timestamp` | posted_at |
| `ownerUsername` | (resolved via candidate_id) |
| (entire object) | raw_data |

### 3.4 comments

Comments on scraped Instagram posts.

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| post_id | UUID | NOT NULL | - | FK -> posts | Parent post |
| scraping_run_id | UUID | NULL | - | FK -> scraping_runs | Run that scraped this comment |
| instagram_id | TEXT | NOT NULL | - | UNIQUE | Instagram comment ID (dedup key) |
| text | TEXT | NOT NULL | - | - | Comment text content |
| author_username | TEXT | NULL | - | - | Comment author username |
| like_count | INTEGER | NOT NULL | 0 | - | Likes on the comment |
| reply_count | INTEGER | NOT NULL | 0 | - | Number of replies |
| commented_at | TIMESTAMPTZ | NULL | - | - | When comment was posted |
| scraped_at | TIMESTAMPTZ | NOT NULL | NOW() | - | When scraped by our system |
| raw_data | JSONB | NULL | - | - | Complete Apify response |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |

**Apify field mapping (instagram-comment-scraper):**

| Apify Field | Database Column |
|-------------|----------------|
| `id` | instagram_id |
| `text` | text |
| `ownerUsername` | author_username |
| `timestamp` | commented_at |
| `likesCount` | like_count |
| `replies` (count) | reply_count |
| (entire object) | raw_data |

### 3.5 sentiment_scores

Sentiment analysis results per comment (1:1 with comments).

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| comment_id | UUID | NOT NULL | - | FK -> comments, UNIQUE | Analyzed comment |
| vader_compound | DOUBLE PRECISION | NOT NULL | - | CHECK [-1.0, 1.0] | VADER compound score |
| vader_positive | DOUBLE PRECISION | NULL | - | CHECK [0.0, 1.0] | VADER positive component |
| vader_negative | DOUBLE PRECISION | NULL | - | CHECK [0.0, 1.0] | VADER negative component |
| vader_neutral | DOUBLE PRECISION | NULL | - | CHECK [0.0, 1.0] | VADER neutral component |
| vader_label | sentiment_label | NOT NULL | - | - | VADER classification |
| llm_label | sentiment_label | NULL | - | - | LLM reclassification (if applicable) |
| llm_confidence | DOUBLE PRECISION | NULL | - | CHECK [0.0, 1.0] | LLM confidence score |
| llm_model | TEXT | NULL | - | - | LLM model used (e.g., gpt-4o-mini) |
| final_label | sentiment_label | NOT NULL | - | - | Resolved label (see logic below) |
| analyzed_at | TIMESTAMPTZ | NOT NULL | NOW() | - | When analysis was performed |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | trigger | Auto-updated on modification |

**Final label resolution logic (PRD FR-003, FR-004):**
```
IF llm_label IS NOT NULL AND llm_confidence >= 0.7:
    final_label = llm_label
ELSE:
    final_label = vader_label
```

### 3.6 themes

Thematic classification of comments (1:N with comments).

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| comment_id | UUID | NOT NULL | - | FK -> comments | Classified comment |
| theme | theme_category | NOT NULL | - | UQ(comment_id, theme, method) | Theme category |
| confidence | DOUBLE PRECISION | NOT NULL | 1.0 | CHECK [0.0, 1.0] | Classification confidence |
| method | analysis_method | NOT NULL | - | UQ(comment_id, theme, method) | Classification method |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |

**Notes:**
- A comment can have multiple themes (e.g., "seguranca" AND "corrupcao")
- The composite unique constraint (comment_id, theme, method) prevents duplicate assignments
- Keyword method always has confidence = 1.0; LLM method has variable confidence

### 3.7 strategic_insights

AI-generated strategic suggestions.

| Column | Type | Nullable | Default | Constraints | Description |
|--------|------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Unique identifier |
| scraping_run_id | UUID | NULL | - | FK -> scraping_runs | Associated run (if any) |
| candidate_id | UUID | NULL | - | FK -> candidates | Target candidate (NULL = both) |
| title | TEXT | NOT NULL | - | - | Suggestion title |
| description | TEXT | NOT NULL | - | - | Detailed suggestion text |
| supporting_data | TEXT | NULL | - | - | Referenced data point |
| priority | TEXT | NOT NULL | 'medium' | CHECK in (high, medium, low) | Priority level |
| llm_model | TEXT | NULL | - | - | LLM model used for generation |
| input_summary | JSONB | NULL | - | - | Analytics context sent to LLM |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | - | Record creation time |

---

## 4. Index Strategy

### Primary Indexes (Query-Critical)

| Index Name | Table | Columns | Type | Justification |
|-----------|-------|---------|------|---------------|
| idx_posts_candidate_id | posts | candidate_id | B-tree | Overview: filter posts by candidate |
| idx_posts_posted_at | posts | posted_at DESC | B-tree | Timeline: chronological ordering |
| idx_posts_candidate_posted_at | posts | (candidate_id, posted_at DESC) | B-tree Composite | Timeline: candidate + date range (most used query) |
| idx_comments_post_id | comments | post_id | B-tree | Join: comments for a post |
| idx_comments_commented_at | comments | commented_at DESC | B-tree | Ordering: recent comments first |
| idx_sentiment_final_label | sentiment_scores | final_label | B-tree | Distribution: count by label |
| idx_themes_theme | themes | theme | B-tree | Distribution: count by theme |

### Secondary Indexes (Operational)

| Index Name | Table | Columns | Type | Justification |
|-----------|-------|---------|------|---------------|
| idx_sentiment_ambiguous | sentiment_scores | vader_compound (partial) | B-tree Partial | LLM fallback: find reclassification candidates |
| idx_themes_comment_id | themes | comment_id | B-tree | Join: themes for a comment |
| idx_themes_theme_method | themes | (theme, method) | B-tree Composite | Filter: themes by classification method |
| idx_scraping_runs_started_at | scraping_runs | started_at DESC | B-tree | Health check: latest runs |
| idx_scraping_runs_status | scraping_runs | status | B-tree | Filter: running/failed runs |
| idx_posts_scraping_run_id | posts | scraping_run_id | B-tree | Join: posts per run |
| idx_comments_scraping_run_id | comments | scraping_run_id | B-tree | Join: comments per run |
| idx_insights_created_at | strategic_insights | created_at DESC | B-tree | Latest insights |
| idx_insights_candidate_id | strategic_insights | candidate_id | B-tree | Filter by candidate |
| idx_insights_priority | strategic_insights | priority | B-tree | Filter by priority |

### Partial Index Detail

```sql
-- Finds ambiguous comments needing LLM reclassification
-- Matches criteria: -0.05 < vader_compound < 0.05 AND no existing LLM label
CREATE INDEX idx_sentiment_ambiguous ON sentiment_scores(vader_compound)
    WHERE llm_label IS NULL
    AND vader_compound > -0.05
    AND vader_compound < 0.05;
```

This partial index is small (only includes ambiguous rows) and speeds up the `get_ambiguous_comments()` function used by the LLM fallback endpoint.

---

## 5. Database Functions

| Function | Parameters | Returns | Used By |
|----------|-----------|---------|---------|
| `get_candidate_overview(UUID)` | candidate_id | overview metrics row | GET /analytics/overview |
| `get_sentiment_timeline(UUID, TIMESTAMPTZ?, TIMESTAMPTZ?)` | candidate_id, start, end | timeline rows | GET /analytics/sentiment-timeline |
| `get_theme_distribution(UUID?)` | candidate_id (optional) | theme counts | GET /analytics/themes |
| `get_post_rankings(UUID?, TEXT, TEXT, INT, INT)` | candidate_id, sort_by, order, limit, offset | ranked posts | GET /analytics/posts |
| `get_comments_text_for_wordcloud(UUID?, INT)` | candidate_id, limit | comment texts | GET /analytics/wordcloud |
| `get_candidate_comparison()` | (none) | comparison rows | GET /analytics/comparison |
| `get_last_successful_scrape()` | (none) | TIMESTAMPTZ | GET /health |
| `get_unanalyzed_comment_ids(INT)` | limit | comment IDs + texts | POST /analysis/sentiment |
| `get_ambiguous_comments(INT)` | limit | ambiguous comments | POST /analysis/sentiment/llm-fallback |
| `update_updated_at_column()` | (trigger) | trigger return | Auto-update updated_at |

---

## 6. RLS Policies

Per PRD CON-005: **No Row-Level Security required for MVP.** This is an internal campaign tool without user authentication.

If RLS is needed in the future (multi-tenancy), the recommended approach is:
- Add a `team_id` column to `candidates`
- Enable RLS on all tables
- Use JWT claims to filter by team_id
- Chain policies through the FK relationships (candidates -> posts -> comments)

---

## 7. Data Volume Estimates

Based on PRD NFR-004:

| Entity | Per Cycle | Growth Rate | After 30 Days |
|--------|-----------|-------------|---------------|
| candidates | 2 (fixed) | 0 | 2 |
| posts | 20 (10 per candidate) | ~20/cycle | ~600 |
| comments | ~10,000 (500 per post) | ~10,000/cycle | ~300,000 |
| sentiment_scores | ~10,000 (1:1 with comments) | ~10,000/cycle | ~300,000 |
| themes | ~15,000 (1.5 per comment avg) | ~15,000/cycle | ~450,000 |
| scraping_runs | 1 per cycle | ~4/day | ~120 |
| strategic_insights | 3-5 per cycle | ~4-5/cycle | ~150 |

**Scraping cycle:** every 6 hours = 4 times/day.

---

## 8. Migration Files

All migrations are in `supabase/migrations/` and must be run in order:

| File | Description | Idempotent |
|------|-------------|------------|
| `001_create_enums.sql` | Custom enum types | No (CREATE TYPE) |
| `002_create_tables.sql` | All tables + triggers | No (CREATE TABLE) |
| `003_create_indexes.sql` | Performance indexes | No (CREATE INDEX) |
| `004_create_functions.sql` | Analytics functions | Yes (CREATE OR REPLACE) |
| `005_seed_data.sql` | Seed candidates | Yes (ON CONFLICT) |

### Running Migrations

**Via Supabase Dashboard (SQL Editor):**
Run each file sequentially in the SQL Editor.

**Via Supabase CLI:**
```bash
supabase db push
```

**Via psql:**
```bash
psql $DATABASE_URL -f supabase/migrations/001_create_enums.sql
psql $DATABASE_URL -f supabase/migrations/002_create_tables.sql
psql $DATABASE_URL -f supabase/migrations/003_create_indexes.sql
psql $DATABASE_URL -f supabase/migrations/004_create_functions.sql
psql $DATABASE_URL -f supabase/migrations/005_seed_data.sql
```

### Rollback Plan

```sql
-- Reverse order teardown (DESTRUCTIVE - use only for full reset)
DROP FUNCTION IF EXISTS get_ambiguous_comments;
DROP FUNCTION IF EXISTS get_unanalyzed_comment_ids;
DROP FUNCTION IF EXISTS get_last_successful_scrape;
DROP FUNCTION IF EXISTS get_candidate_comparison;
DROP FUNCTION IF EXISTS get_comments_text_for_wordcloud;
DROP FUNCTION IF EXISTS get_post_rankings;
DROP FUNCTION IF EXISTS get_theme_distribution;
DROP FUNCTION IF EXISTS get_sentiment_timeline;
DROP FUNCTION IF EXISTS get_candidate_overview;
DROP FUNCTION IF EXISTS update_updated_at_column;

DROP TABLE IF EXISTS strategic_insights CASCADE;
DROP TABLE IF EXISTS themes CASCADE;
DROP TABLE IF EXISTS sentiment_scores CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS scraping_runs CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;

DROP TYPE IF EXISTS media_type;
DROP TYPE IF EXISTS analysis_method;
DROP TYPE IF EXISTS theme_category;
DROP TYPE IF EXISTS scraping_status;
DROP TYPE IF EXISTS sentiment_label;
```

---

## 9. Upsert Patterns

The application uses upsert (INSERT ON CONFLICT) for idempotent scraping:

### Posts Upsert
```sql
INSERT INTO posts (candidate_id, instagram_id, url, caption, like_count, comment_count, ...)
VALUES (...)
ON CONFLICT (instagram_id) DO UPDATE SET
    like_count = EXCLUDED.like_count,
    comment_count = EXCLUDED.comment_count,
    scraped_at = NOW(),
    updated_at = NOW();
```

### Comments Upsert
```sql
INSERT INTO comments (post_id, instagram_id, text, author_username, like_count, ...)
VALUES (...)
ON CONFLICT (instagram_id) DO UPDATE SET
    like_count = EXCLUDED.like_count,
    scraped_at = NOW();
```

These patterns ensure that re-scraping the same content updates engagement metrics without creating duplicates.

---

## 10. Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0.0 | Initial schema design | Dara (Data Engineer) |

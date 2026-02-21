-- ============================================================================
-- Migration 003: Create Indexes
-- Instagram Campaign Analytics
-- Created: 2026-02-21
-- Description: Performance indexes for all query patterns required by
--              the analytics endpoints (FR-006 through FR-011).
-- Depends on: 002_create_tables.sql
-- ============================================================================

-- ============================================================================
-- posts indexes
-- ============================================================================

-- Primary lookup: all posts for a candidate (overview, post listing)
-- Used by: GET /analytics/overview, GET /analytics/posts
CREATE INDEX idx_posts_candidate_id ON posts(candidate_id);

-- Temporal queries: sentiment timeline, date range filtering
-- Used by: GET /analytics/sentiment-timeline
CREATE INDEX idx_posts_posted_at ON posts(posted_at DESC);

-- Composite: candidate + time range (most common query pattern)
-- Used by: GET /analytics/sentiment-timeline?candidate_id=X&start_date=Y&end_date=Z
CREATE INDEX idx_posts_candidate_posted_at ON posts(candidate_id, posted_at DESC);

-- Deduplication during upsert: lookup by instagram_id
-- Already covered by UNIQUE constraint on instagram_id

-- Scraping run reference
CREATE INDEX idx_posts_scraping_run_id ON posts(scraping_run_id);

-- ============================================================================
-- comments indexes
-- ============================================================================

-- Primary lookup: all comments for a post
-- Used by: analytics aggregations, word cloud generation
CREATE INDEX idx_comments_post_id ON comments(post_id);

-- Temporal ordering of comments
CREATE INDEX idx_comments_commented_at ON comments(commented_at DESC);

-- Scraping run reference
CREATE INDEX idx_comments_scraping_run_id ON comments(scraping_run_id);

-- Text search support for word cloud (GIN trigram index)
-- Enables efficient text analysis without full-text search overhead
-- CREATE INDEX idx_comments_text_trgm ON comments USING gin(text gin_trgm_ops);
-- Note: Requires pg_trgm extension. Uncomment if needed for performance.

-- ============================================================================
-- sentiment_scores indexes
-- ============================================================================

-- 1:1 lookup by comment
-- Already covered by UNIQUE constraint on comment_id

-- Filter by final sentiment label (for distribution counts)
-- Used by: GET /analytics/overview (sentiment distribution)
CREATE INDEX idx_sentiment_final_label ON sentiment_scores(final_label);

-- Find ambiguous comments needing LLM reclassification
-- Used by: POST /analysis/sentiment/llm-fallback
CREATE INDEX idx_sentiment_ambiguous ON sentiment_scores(vader_compound)
    WHERE llm_label IS NULL
    AND vader_compound > -0.05
    AND vader_compound < 0.05;

-- ============================================================================
-- themes indexes
-- ============================================================================

-- Filter by theme category (for theme distribution charts)
-- Used by: GET /analytics/themes
CREATE INDEX idx_themes_theme ON themes(theme);

-- Lookup themes for a specific comment
CREATE INDEX idx_themes_comment_id ON themes(comment_id);

-- Composite: theme + method (for filtering by classification method)
CREATE INDEX idx_themes_theme_method ON themes(theme, method);

-- ============================================================================
-- scraping_runs indexes
-- ============================================================================

-- Find latest runs (for health check, dashboard last-update)
-- Used by: GET /health
CREATE INDEX idx_scraping_runs_started_at ON scraping_runs(started_at DESC);

-- Filter by status (find running, failed runs)
CREATE INDEX idx_scraping_runs_status ON scraping_runs(status);

-- ============================================================================
-- strategic_insights indexes
-- ============================================================================

-- Latest insights (for insights view)
CREATE INDEX idx_insights_created_at ON strategic_insights(created_at DESC);

-- Filter by candidate
CREATE INDEX idx_insights_candidate_id ON strategic_insights(candidate_id);

-- Filter by priority
CREATE INDEX idx_insights_priority ON strategic_insights(priority);

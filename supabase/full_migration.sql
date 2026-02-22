-- ============================================================================
-- Migration 001: Create Enums
-- Instagram Campaign Analytics
-- Created: 2026-02-21
-- Description: Custom enum types for sentiment labels, scraping status,
--              theme categories, and analysis methods.
-- ============================================================================

-- Sentiment classification labels
-- Used in sentiment_scores.vader_label, sentiment_scores.llm_label,
-- and sentiment_scores.final_label
CREATE TYPE sentiment_label AS ENUM (
    'positive',
    'negative',
    'neutral'
);

-- Scraping run status tracking
-- Used in scraping_runs.status
CREATE TYPE scraping_status AS ENUM (
    'running',
    'success',
    'failed',
    'partial'
);

-- Predefined theme categories for comment classification
-- Based on PRD FR-009: saude, seguranca, educacao, economia, infraestrutura,
-- corrupcao, emprego, meio_ambiente, outros
CREATE TYPE theme_category AS ENUM (
    'saude',
    'seguranca',
    'educacao',
    'economia',
    'infraestrutura',
    'corrupcao',
    'emprego',
    'meio_ambiente',
    'outros'
);

-- Method used for theme extraction
-- Used in themes.method
CREATE TYPE analysis_method AS ENUM (
    'keyword',
    'llm'
);

-- Media type for Instagram posts
CREATE TYPE media_type AS ENUM (
    'image',
    'video',
    'carousel',
    'unknown'
);

COMMENT ON TYPE sentiment_label IS 'Sentiment classification: positive (>= 0.05), negative (<= -0.05), neutral (between)';
COMMENT ON TYPE scraping_status IS 'Lifecycle status of a scraping run';
COMMENT ON TYPE theme_category IS 'Predefined thematic categories for comment classification (PT-BR political context)';
COMMENT ON TYPE analysis_method IS 'Method used for classification: keyword-based or LLM-based';
COMMENT ON TYPE media_type IS 'Instagram post media type';
-- ============================================================================
-- Migration 002: Create Tables
-- Instagram Campaign Analytics
-- Created: 2026-02-21
-- Description: Core tables for candidates, posts, comments, sentiment scores,
--              themes, scraping runs, and strategic insights.
-- Depends on: 001_create_enums.sql
-- ============================================================================

-- Enable uuid-ossp extension for gen_random_uuid() if not already available
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- Table: candidates
-- Description: Monitored Instagram candidate profiles.
--              MVP: exactly 2 candidates (@charlles.evangelista, @delegadasheila)
-- PRD: CON-002, FR-005
-- ============================================================================
CREATE TABLE candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    profile_url     TEXT GENERATED ALWAYS AS ('https://www.instagram.com/' || username || '/') STORED,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE candidates IS 'Monitored Instagram candidate profiles for campaign analytics';
COMMENT ON COLUMN candidates.username IS 'Instagram username without @ prefix';
COMMENT ON COLUMN candidates.profile_url IS 'Auto-generated Instagram profile URL';
COMMENT ON COLUMN candidates.is_active IS 'Whether this candidate is actively being scraped';

-- ============================================================================
-- Table: scraping_runs
-- Description: Log of each scraping execution cycle.
--              Tracks timing, status, counts, and errors.
-- PRD: NFR-005, NFR-008
-- ============================================================================
CREATE TABLE scraping_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    status              scraping_status NOT NULL DEFAULT 'running',
    posts_scraped       INTEGER NOT NULL DEFAULT 0,
    comments_scraped    INTEGER NOT NULL DEFAULT 0,
    duration_seconds    NUMERIC(10, 2),
    errors              JSONB,
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE scraping_runs IS 'Audit log of scraping pipeline executions';
COMMENT ON COLUMN scraping_runs.duration_seconds IS 'Total wall-clock time of the scraping run';
COMMENT ON COLUMN scraping_runs.errors IS 'Array of error objects: [{candidate, phase, message, timestamp}]';
COMMENT ON COLUMN scraping_runs.metadata IS 'Additional run metadata (apify actor IDs, config used, etc.)';

-- ============================================================================
-- Table: posts
-- Description: Instagram posts scraped from candidate profiles.
--              Maps 1:1 to Apify instagram-post-scraper output.
-- PRD: FR-001, FR-005
-- ============================================================================
CREATE TABLE posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id    UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    scraping_run_id UUID REFERENCES scraping_runs(id) ON DELETE SET NULL,
    instagram_id    TEXT UNIQUE NOT NULL,
    url             TEXT NOT NULL,
    shortcode       TEXT,
    caption         TEXT,
    like_count      INTEGER NOT NULL DEFAULT 0,
    comment_count   INTEGER NOT NULL DEFAULT 0,
    media_type      media_type NOT NULL DEFAULT 'unknown',
    is_sponsored    BOOLEAN NOT NULL DEFAULT FALSE,
    video_view_count INTEGER,
    posted_at       TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_data        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE posts IS 'Instagram posts scraped from monitored candidate profiles';
COMMENT ON COLUMN posts.instagram_id IS 'Unique Instagram post identifier (used for deduplication on upsert)';
COMMENT ON COLUMN posts.shortcode IS 'Instagram post shortcode extracted from URL';
COMMENT ON COLUMN posts.raw_data IS 'Complete raw JSON response from Apify scraper for this post';

-- ============================================================================
-- Table: comments
-- Description: Comments on scraped Instagram posts.
--              Maps to Apify instagram-comment-scraper output.
-- PRD: FR-002, FR-005
-- ============================================================================
CREATE TABLE comments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    scraping_run_id     UUID REFERENCES scraping_runs(id) ON DELETE SET NULL,
    instagram_id        TEXT UNIQUE NOT NULL,
    text                TEXT NOT NULL,
    author_username     TEXT,
    like_count          INTEGER NOT NULL DEFAULT 0,
    reply_count         INTEGER NOT NULL DEFAULT 0,
    commented_at        TIMESTAMPTZ,
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_data            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE comments IS 'Comments on scraped Instagram posts';
COMMENT ON COLUMN comments.instagram_id IS 'Unique Instagram comment identifier (used for deduplication on upsert)';
COMMENT ON COLUMN comments.reply_count IS 'Number of replies to this comment (from Apify data)';
COMMENT ON COLUMN comments.raw_data IS 'Complete raw JSON response from Apify scraper for this comment';

-- ============================================================================
-- Table: sentiment_scores
-- Description: Sentiment analysis results per comment.
--              1:1 relationship with comments.
--              VADER provides baseline; LLM provides fallback for ambiguous cases.
-- PRD: FR-003, FR-004, FR-005
-- ============================================================================
CREATE TABLE sentiment_scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id          UUID UNIQUE NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    vader_compound      DOUBLE PRECISION NOT NULL,
    vader_positive      DOUBLE PRECISION,
    vader_negative      DOUBLE PRECISION,
    vader_neutral       DOUBLE PRECISION,
    vader_label         sentiment_label NOT NULL,
    llm_label           sentiment_label,
    llm_confidence      DOUBLE PRECISION,
    llm_model           TEXT,
    final_label         sentiment_label NOT NULL,
    analyzed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_vader_compound_range CHECK (vader_compound BETWEEN -1.0 AND 1.0),
    CONSTRAINT chk_llm_confidence_range CHECK (llm_confidence IS NULL OR llm_confidence BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_vader_scores_range CHECK (
        (vader_positive IS NULL OR vader_positive BETWEEN 0.0 AND 1.0)
        AND (vader_negative IS NULL OR vader_negative BETWEEN 0.0 AND 1.0)
        AND (vader_neutral IS NULL OR vader_neutral BETWEEN 0.0 AND 1.0)
    )
);

COMMENT ON TABLE sentiment_scores IS 'Sentiment analysis results: VADER baseline + optional LLM reclassification';
COMMENT ON COLUMN sentiment_scores.vader_compound IS 'VADER compound score (-1.0 to 1.0)';
COMMENT ON COLUMN sentiment_scores.vader_label IS 'Classification from VADER: positive (>=0.05), negative (<=-0.05), neutral';
COMMENT ON COLUMN sentiment_scores.llm_label IS 'Reclassification from LLM (NULL if VADER was unambiguous)';
COMMENT ON COLUMN sentiment_scores.llm_confidence IS 'LLM confidence score (0.0-1.0). final_label uses LLM when >= 0.7';
COMMENT ON COLUMN sentiment_scores.llm_model IS 'LLM model identifier used for reclassification (e.g., gpt-4o-mini)';
COMMENT ON COLUMN sentiment_scores.final_label IS 'Resolved sentiment: LLM label if confidence >= 0.7, else VADER label';

-- ============================================================================
-- Table: themes
-- Description: Thematic classification of comments.
--              A comment may have multiple themes (1:N).
-- PRD: FR-009
-- ============================================================================
CREATE TABLE themes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id      UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    theme           theme_category NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    method          analysis_method NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate theme assignments per comment per method
    CONSTRAINT uq_comment_theme_method UNIQUE (comment_id, theme, method),
    CONSTRAINT chk_theme_confidence_range CHECK (confidence BETWEEN 0.0 AND 1.0)
);

COMMENT ON TABLE themes IS 'Thematic classification of comments (saude, seguranca, educacao, etc.)';
COMMENT ON COLUMN themes.confidence IS 'Classification confidence (1.0 for keyword match, 0.0-1.0 for LLM)';
COMMENT ON COLUMN themes.method IS 'Classification method: keyword-based or LLM-based';

-- ============================================================================
-- Table: strategic_insights
-- Description: AI-generated strategic suggestions stored for history.
--              Generated per scraping cycle or on demand.
-- PRD: FR-012
-- ============================================================================
CREATE TABLE strategic_insights (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraping_run_id     UUID REFERENCES scraping_runs(id) ON DELETE SET NULL,
    candidate_id        UUID REFERENCES candidates(id) ON DELETE SET NULL,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    supporting_data     TEXT,
    priority            TEXT NOT NULL DEFAULT 'medium',
    llm_model           TEXT,
    input_summary       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_priority_values CHECK (priority IN ('high', 'medium', 'low'))
);

COMMENT ON TABLE strategic_insights IS 'AI-generated strategic suggestions based on analytics data';
COMMENT ON COLUMN strategic_insights.candidate_id IS 'NULL means insight applies to both/all candidates';
COMMENT ON COLUMN strategic_insights.supporting_data IS 'Specific data point referenced by the suggestion';
COMMENT ON COLUMN strategic_insights.input_summary IS 'Analytics summary sent to LLM as input context';

-- ============================================================================
-- Triggers: updated_at auto-update
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_sentiment_scores_updated_at
    BEFORE UPDATE ON sentiment_scores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
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
-- ============================================================================
-- Migration 004: Create Functions
-- Instagram Campaign Analytics
-- Created: 2026-02-21
-- Description: Database functions for analytics aggregations and common
--              query patterns used by the API endpoints.
-- Depends on: 002_create_tables.sql, 003_create_indexes.sql
-- ============================================================================

-- ============================================================================
-- Function: get_candidate_overview
-- Description: Returns aggregated overview metrics for a single candidate.
-- Used by: GET /api/v1/analytics/overview
-- ============================================================================
CREATE OR REPLACE FUNCTION get_candidate_overview(p_candidate_id UUID)
RETURNS TABLE (
    candidate_id        UUID,
    username            TEXT,
    display_name        TEXT,
    total_posts         BIGINT,
    total_comments      BIGINT,
    total_engagement    BIGINT,
    avg_sentiment       DOUBLE PRECISION,
    positive_count      BIGINT,
    negative_count      BIGINT,
    neutral_count       BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS candidate_id,
        c.username,
        c.display_name,
        COUNT(DISTINCT p.id) AS total_posts,
        COUNT(DISTINCT cm.id) AS total_comments,
        COALESCE(SUM(DISTINCT p.like_count), 0) + COUNT(DISTINCT cm.id) AS total_engagement,
        COALESCE(AVG(ss.vader_compound), 0.0) AS avg_sentiment,
        COUNT(CASE WHEN ss.final_label = 'positive' THEN 1 END) AS positive_count,
        COUNT(CASE WHEN ss.final_label = 'negative' THEN 1 END) AS negative_count,
        COUNT(CASE WHEN ss.final_label = 'neutral' THEN 1 END) AS neutral_count
    FROM candidates c
    LEFT JOIN posts p ON p.candidate_id = c.id
    LEFT JOIN comments cm ON cm.post_id = p.id
    LEFT JOIN sentiment_scores ss ON ss.comment_id = cm.id
    WHERE c.id = p_candidate_id
    GROUP BY c.id, c.username, c.display_name;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_candidate_overview IS 'Aggregate overview metrics for a single candidate: posts, comments, engagement, sentiment distribution';

-- ============================================================================
-- Function: get_sentiment_timeline
-- Description: Returns sentiment scores over time for a candidate,
--              aggregated per post.
-- Used by: GET /api/v1/analytics/sentiment-timeline
-- ============================================================================
CREATE OR REPLACE FUNCTION get_sentiment_timeline(
    p_candidate_id UUID,
    p_start_date TIMESTAMPTZ DEFAULT NULL,
    p_end_date TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
    post_id         UUID,
    post_url        TEXT,
    post_caption    TEXT,
    posted_at       TIMESTAMPTZ,
    avg_sentiment   DOUBLE PRECISION,
    comment_count   BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id AS post_id,
        p.url AS post_url,
        LEFT(p.caption, 100) AS post_caption,
        p.posted_at,
        COALESCE(AVG(ss.vader_compound), 0.0) AS avg_sentiment,
        COUNT(cm.id) AS comment_count
    FROM posts p
    LEFT JOIN comments cm ON cm.post_id = p.id
    LEFT JOIN sentiment_scores ss ON ss.comment_id = cm.id
    WHERE p.candidate_id = p_candidate_id
      AND (p_start_date IS NULL OR p.posted_at >= p_start_date)
      AND (p_end_date IS NULL OR p.posted_at <= p_end_date)
    GROUP BY p.id, p.url, p.caption, p.posted_at
    ORDER BY p.posted_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_sentiment_timeline IS 'Sentiment score timeline per post for a candidate, with optional date range filter';

-- ============================================================================
-- Function: get_theme_distribution
-- Description: Returns theme distribution (counts and percentages) for
--              a candidate or all candidates.
-- Used by: GET /api/v1/analytics/themes
-- ============================================================================
CREATE OR REPLACE FUNCTION get_theme_distribution(
    p_candidate_id UUID DEFAULT NULL
)
RETURNS TABLE (
    theme           theme_category,
    comment_count   BIGINT,
    percentage      DOUBLE PRECISION
) AS $$
DECLARE
    v_total BIGINT;
BEGIN
    -- Get total themed comments for percentage calculation
    SELECT COUNT(*) INTO v_total
    FROM themes t
    JOIN comments cm ON cm.id = t.comment_id
    JOIN posts p ON p.id = cm.post_id
    WHERE p_candidate_id IS NULL OR p.candidate_id = p_candidate_id;

    IF v_total = 0 THEN
        v_total := 1; -- Avoid division by zero
    END IF;

    RETURN QUERY
    SELECT
        t.theme,
        COUNT(*) AS comment_count,
        ROUND((COUNT(*)::DOUBLE PRECISION / v_total) * 100, 2) AS percentage
    FROM themes t
    JOIN comments cm ON cm.id = t.comment_id
    JOIN posts p ON p.id = cm.post_id
    WHERE p_candidate_id IS NULL OR p.candidate_id = p_candidate_id
    GROUP BY t.theme
    ORDER BY comment_count DESC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_theme_distribution IS 'Theme distribution with counts and percentages, filterable by candidate';

-- ============================================================================
-- Function: get_post_rankings
-- Description: Returns posts ranked by engagement metrics.
-- Used by: GET /api/v1/analytics/posts
-- ============================================================================
CREATE OR REPLACE FUNCTION get_post_rankings(
    p_candidate_id UUID DEFAULT NULL,
    p_sort_by TEXT DEFAULT 'comment_count',
    p_sort_order TEXT DEFAULT 'desc',
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    post_id             UUID,
    candidate_username  TEXT,
    url                 TEXT,
    caption_preview     TEXT,
    like_count          INTEGER,
    comment_count       INTEGER,
    avg_sentiment       DOUBLE PRECISION,
    positive_ratio      DOUBLE PRECISION,
    negative_ratio      DOUBLE PRECISION,
    posted_at           TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id AS post_id,
        c.username AS candidate_username,
        p.url,
        LEFT(p.caption, 80) AS caption_preview,
        p.like_count,
        p.comment_count,
        COALESCE(AVG(ss.vader_compound), 0.0) AS avg_sentiment,
        CASE WHEN COUNT(ss.id) = 0 THEN 0.0
             ELSE COUNT(CASE WHEN ss.final_label = 'positive' THEN 1 END)::DOUBLE PRECISION / COUNT(ss.id)
        END AS positive_ratio,
        CASE WHEN COUNT(ss.id) = 0 THEN 0.0
             ELSE COUNT(CASE WHEN ss.final_label = 'negative' THEN 1 END)::DOUBLE PRECISION / COUNT(ss.id)
        END AS negative_ratio,
        p.posted_at
    FROM posts p
    JOIN candidates c ON c.id = p.candidate_id
    LEFT JOIN comments cm ON cm.post_id = p.id
    LEFT JOIN sentiment_scores ss ON ss.comment_id = cm.id
    WHERE p_candidate_id IS NULL OR p.candidate_id = p_candidate_id
    GROUP BY p.id, c.username, p.url, p.caption, p.like_count, p.comment_count, p.posted_at
    ORDER BY
        CASE WHEN p_sort_by = 'comment_count' AND p_sort_order = 'desc' THEN p.comment_count END DESC NULLS LAST,
        CASE WHEN p_sort_by = 'comment_count' AND p_sort_order = 'asc' THEN p.comment_count END ASC NULLS LAST,
        CASE WHEN p_sort_by = 'like_count' AND p_sort_order = 'desc' THEN p.like_count END DESC NULLS LAST,
        CASE WHEN p_sort_by = 'like_count' AND p_sort_order = 'asc' THEN p.like_count END ASC NULLS LAST,
        CASE WHEN p_sort_by = 'posted_at' AND p_sort_order = 'desc' THEN p.posted_at END DESC NULLS LAST,
        CASE WHEN p_sort_by = 'posted_at' AND p_sort_order = 'asc' THEN p.posted_at END ASC NULLS LAST,
        p.comment_count DESC NULLS LAST  -- default fallback
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_post_rankings IS 'Ranked post listing with engagement metrics, sortable and filterable';

-- ============================================================================
-- Function: get_word_frequencies
-- Description: Returns word frequencies from comments for word cloud.
--              Excludes Portuguese stop words.
-- Used by: GET /api/v1/analytics/wordcloud
-- Note: This is a helper function. The heavy lifting of stop word removal
--        and tokenization is better done in Python (app layer). This function
--        provides the raw comment texts for processing.
-- ============================================================================
CREATE OR REPLACE FUNCTION get_comments_text_for_wordcloud(
    p_candidate_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 10000
)
RETURNS TABLE (
    comment_text TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT cm.text AS comment_text
    FROM comments cm
    JOIN posts p ON p.id = cm.post_id
    WHERE (p_candidate_id IS NULL OR p.candidate_id = p_candidate_id)
      AND cm.text IS NOT NULL
      AND LENGTH(cm.text) > 3
    ORDER BY cm.commented_at DESC NULLS LAST
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_comments_text_for_wordcloud IS 'Fetch comment texts for word cloud generation (tokenization done in app layer)';

-- ============================================================================
-- Function: get_candidate_comparison
-- Description: Returns side-by-side comparison data for all active candidates.
-- Used by: GET /api/v1/analytics/comparison
-- ============================================================================
CREATE OR REPLACE FUNCTION get_candidate_comparison()
RETURNS TABLE (
    candidate_id        UUID,
    username            TEXT,
    display_name        TEXT,
    total_posts         BIGINT,
    total_comments      BIGINT,
    total_engagement    BIGINT,
    avg_sentiment       DOUBLE PRECISION,
    positive_count      BIGINT,
    negative_count      BIGINT,
    neutral_count       BIGINT,
    recent_avg_sentiment DOUBLE PRECISION,
    previous_avg_sentiment DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    WITH post_sentiments AS (
        SELECT
            p.candidate_id,
            p.id AS post_id,
            p.posted_at,
            p.like_count,
            AVG(ss.vader_compound) AS post_avg_sentiment,
            ROW_NUMBER() OVER (PARTITION BY p.candidate_id ORDER BY p.posted_at DESC) AS rn
        FROM posts p
        LEFT JOIN comments cm ON cm.post_id = p.id
        LEFT JOIN sentiment_scores ss ON ss.comment_id = cm.id
        GROUP BY p.candidate_id, p.id, p.posted_at, p.like_count
    ),
    recent_5 AS (
        SELECT candidate_id, AVG(post_avg_sentiment) AS avg_sent
        FROM post_sentiments WHERE rn <= 5
        GROUP BY candidate_id
    ),
    previous_5 AS (
        SELECT candidate_id, AVG(post_avg_sentiment) AS avg_sent
        FROM post_sentiments WHERE rn > 5 AND rn <= 10
        GROUP BY candidate_id
    )
    SELECT
        c.id AS candidate_id,
        c.username,
        c.display_name,
        COUNT(DISTINCT p.id) AS total_posts,
        COUNT(DISTINCT cm.id) AS total_comments,
        COALESCE(SUM(DISTINCT p.like_count), 0) + COUNT(DISTINCT cm.id) AS total_engagement,
        COALESCE(AVG(ss.vader_compound), 0.0) AS avg_sentiment,
        COUNT(CASE WHEN ss.final_label = 'positive' THEN 1 END) AS positive_count,
        COUNT(CASE WHEN ss.final_label = 'negative' THEN 1 END) AS negative_count,
        COUNT(CASE WHEN ss.final_label = 'neutral' THEN 1 END) AS neutral_count,
        COALESCE(r5.avg_sent, 0.0) AS recent_avg_sentiment,
        COALESCE(p5.avg_sent, 0.0) AS previous_avg_sentiment
    FROM candidates c
    LEFT JOIN posts p ON p.candidate_id = c.id
    LEFT JOIN comments cm ON cm.post_id = p.id
    LEFT JOIN sentiment_scores ss ON ss.comment_id = cm.id
    LEFT JOIN recent_5 r5 ON r5.candidate_id = c.id
    LEFT JOIN previous_5 p5 ON p5.candidate_id = c.id
    WHERE c.is_active = TRUE
    GROUP BY c.id, c.username, c.display_name, r5.avg_sent, p5.avg_sent
    ORDER BY c.username ASC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_candidate_comparison IS 'Side-by-side comparison metrics for all active candidates with trend direction';

-- ============================================================================
-- Function: get_last_successful_scrape
-- Description: Returns timestamp of the last successful scraping run.
-- Used by: GET /api/v1/health
-- ============================================================================
CREATE OR REPLACE FUNCTION get_last_successful_scrape()
RETURNS TIMESTAMPTZ AS $$
BEGIN
    RETURN (
        SELECT completed_at
        FROM scraping_runs
        WHERE status = 'success'
        ORDER BY completed_at DESC
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_last_successful_scrape IS 'Timestamp of the most recent successful scraping run (for health check)';

-- ============================================================================
-- Function: get_unanalyzed_comment_ids
-- Description: Returns comment IDs that do not yet have sentiment scores.
-- Used by: POST /api/v1/analysis/sentiment (batch processing)
-- ============================================================================
CREATE OR REPLACE FUNCTION get_unanalyzed_comment_ids(p_limit INTEGER DEFAULT 1000)
RETURNS TABLE (comment_id UUID, comment_text TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT cm.id, cm.text
    FROM comments cm
    LEFT JOIN sentiment_scores ss ON ss.comment_id = cm.id
    WHERE ss.id IS NULL
    ORDER BY cm.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_unanalyzed_comment_ids IS 'Find comments that have not yet been analyzed for sentiment';

-- ============================================================================
-- Function: get_ambiguous_comments
-- Description: Returns comments eligible for LLM reclassification.
--              Criteria: VADER compound between -0.05 and 0.05, text > 20 chars,
--              and no existing LLM label.
-- Used by: POST /api/v1/analysis/sentiment/llm-fallback
-- ============================================================================
CREATE OR REPLACE FUNCTION get_ambiguous_comments(p_limit INTEGER DEFAULT 500)
RETURNS TABLE (
    comment_id      UUID,
    comment_text    TEXT,
    vader_compound  DOUBLE PRECISION,
    sentiment_id    UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cm.id AS comment_id,
        cm.text AS comment_text,
        ss.vader_compound,
        ss.id AS sentiment_id
    FROM comments cm
    JOIN sentiment_scores ss ON ss.comment_id = cm.id
    WHERE ss.llm_label IS NULL
      AND ss.vader_compound > -0.05
      AND ss.vader_compound < 0.05
      AND LENGTH(cm.text) > 20
    ORDER BY cm.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_ambiguous_comments IS 'Find comments with ambiguous VADER scores eligible for LLM reclassification';
-- ============================================================================
-- Migration 005: Seed Data
-- Instagram Campaign Analytics
-- Created: 2026-02-21
-- Description: Initial seed data for the two monitored candidates.
-- Depends on: 002_create_tables.sql
-- PRD: CON-002 (exactly 2 profiles for MVP)
-- ============================================================================

-- Insert monitored candidates
-- Using ON CONFLICT to make this script idempotent (safe to re-run)
INSERT INTO candidates (username, display_name, is_active)
VALUES
    ('charlles.evangelista', 'Charlles Evangelista', TRUE),
    ('delegadasheila', 'Delegada Sheila', TRUE)
ON CONFLICT (username) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

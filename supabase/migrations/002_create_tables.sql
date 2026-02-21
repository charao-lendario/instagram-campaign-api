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

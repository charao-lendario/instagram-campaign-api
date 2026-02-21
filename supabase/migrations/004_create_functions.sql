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

-- 001_initial_schema.sql
-- Instagram Campaign Analytics - Initial Schema
-- PRD References: FR-005, CON-005, NFR-004
-- Architecture Reference: docs/architecture/architecture.md Section 5

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

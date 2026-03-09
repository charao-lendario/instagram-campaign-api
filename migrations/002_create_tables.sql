CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scraping_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status scraping_status DEFAULT 'running',
    posts_scraped INT DEFAULT 0,
    comments_scraped INT DEFAULT 0,
    duration_seconds NUMERIC(10,2),
    errors JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    scraping_run_id UUID REFERENCES scraping_runs(id) ON DELETE SET NULL,
    instagram_id TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    shortcode TEXT,
    caption TEXT,
    like_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    media_type media_type DEFAULT 'unknown',
    is_sponsored BOOLEAN DEFAULT FALSE,
    video_view_count INT,
    posted_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    scraping_run_id UUID REFERENCES scraping_runs(id) ON DELETE SET NULL,
    instagram_id TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    author_username TEXT,
    like_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    commented_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sentiment_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID UNIQUE NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    vader_compound DOUBLE PRECISION NOT NULL,
    vader_positive DOUBLE PRECISION,
    vader_negative DOUBLE PRECISION,
    vader_neutral DOUBLE PRECISION,
    vader_label sentiment_label NOT NULL,
    llm_label sentiment_label,
    llm_confidence DOUBLE PRECISION,
    llm_model TEXT,
    final_label sentiment_label NOT NULL,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS themes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    theme theme_category NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    method analysis_method NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (comment_id, theme, method)
);

CREATE TABLE IF NOT EXISTS strategic_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraping_run_id UUID REFERENCES scraping_runs(id) ON DELETE SET NULL,
    candidate_id UUID REFERENCES candidates(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    supporting_data TEXT,
    priority TEXT CHECK (priority IN ('high', 'medium', 'low')) DEFAULT 'medium',
    llm_model TEXT,
    input_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

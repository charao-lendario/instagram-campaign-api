CREATE INDEX IF NOT EXISTS idx_posts_candidate_id ON posts(candidate_id);
CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_candidate_posted_at ON posts(candidate_id, posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_final_label ON sentiment_scores(final_label);
CREATE INDEX IF NOT EXISTS idx_themes_theme ON themes(theme);
CREATE INDEX IF NOT EXISTS idx_themes_comment_id ON themes(comment_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_ambiguous ON sentiment_scores(vader_compound) WHERE llm_label IS NULL;
CREATE INDEX IF NOT EXISTS idx_scraping_runs_started_at ON scraping_runs(started_at DESC);

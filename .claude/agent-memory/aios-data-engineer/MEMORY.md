# Data Engineer Agent Memory

## Project: Instagram Campaign Analytics

### Database
- **Provider:** Supabase PostgreSQL
- **RLS:** Not required for MVP (internal tool, CON-005)
- **Client:** supabase-py (no ORM, CON-003)
- **Schema doc:** `/Users/lucascharao/instagram-campaign-api/docs/architecture/SCHEMA.md`
- **Migrations:** `/Users/lucascharao/instagram-campaign-api/supabase/migrations/001-005`

### Schema Overview (v1.0.0)
- 7 tables: candidates, posts, comments, sentiment_scores, themes, scraping_runs, strategic_insights
- 5 enums: sentiment_label, scraping_status, theme_category, analysis_method, media_type
- 9 database functions for analytics endpoints
- Deduplication via instagram_id UNIQUE on posts and comments (upsert pattern)
- JSONB raw_data columns on posts/comments for full Apify response preservation

### Key Design Decisions
- `final_label` resolution: LLM label wins if confidence >= 0.7, else VADER label
- themes is 1:N with comments (a comment can have multiple themes)
- Composite unique (comment_id, theme, method) prevents duplicate theme assignments
- Partial index on sentiment_scores for ambiguous comments (LLM fallback query optimization)
- CASCADE delete from candidates->posts->comments->sentiment_scores/themes
- SET NULL on scraping_run_id FKs (preserve data if run record deleted)
- Generated column profile_url on candidates

### Candidates (Seed Data)
- charlles.evangelista / Charlles Evangelista
- delegadasheila / Delegada Sheila

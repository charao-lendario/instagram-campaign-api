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

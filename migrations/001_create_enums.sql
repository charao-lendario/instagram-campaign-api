DO $$ BEGIN
    CREATE TYPE sentiment_label AS ENUM ('positive', 'negative', 'neutral');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE scraping_status AS ENUM ('running', 'success', 'failed', 'partial');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE theme_category AS ENUM (
        'saude', 'seguranca', 'educacao', 'economia',
        'infraestrutura', 'corrupcao', 'emprego', 'meio_ambiente', 'outros'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE analysis_method AS ENUM ('keyword', 'llm');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE media_type AS ENUM ('image', 'video', 'carousel', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

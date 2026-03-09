# Architect Agent Memory - Instagram Campaign Analytics

## Project Overview
- **Type:** Instagram scraping + sentiment analysis + dashboard (political campaign tool)
- **Stack:** FastAPI (Railway) + Next.js 16 (Vercel) + Supabase PostgreSQL + Apify + VADER + OpenAI
- **Repos:** `instagram-campaign-api` (backend) / `instagram-campaign-web` (frontend, separate repo)
- **Key constraint:** No ORM (CON-003), Supabase SDK directly

## Architecture Document
- Created: `/Users/lucascharao/instagram-campaign-api/docs/architecture/architecture.md`
- SQL migration: `/Users/lucascharao/instagram-campaign-api/docs/architecture/migrations/001_initial_schema.sql`
- 15 API endpoints documented with full request/response schemas
- 6 database tables, 8 indexes

## Key Decisions
- VADER + LLM fallback for sentiment (cost control: ~85% free, 15% GPT-4o-mini)
- APScheduler in-process (no external queue, single-process Railway deploy)
- threading.Lock for pipeline concurrency control
- Pydantic models for all request/response validation (no ORM)

## Gotchas
- Current Dockerfile uses python:3.12-slim; production needs python:3.11-slim per CON-003
- CORS is wildcard in scaffolding; must lock to Vercel domain in production
- .env.example references OPENAI_API_KEY but architecture uses LLM_PROVIDER/LLM_MODEL/LLM_API_KEY pattern

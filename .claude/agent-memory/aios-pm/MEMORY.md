# PM Agent Memory - Instagram Campaign Analytics

## Project Structure
- **API repo**: `/Users/lucascharao/instagram-campaign-api` (FastAPI, Railway)
- **Web repo**: `/Users/lucascharao/instagram-campaign-web` (Next.js, Vercel)
- **Database**: Supabase PostgreSQL
- **Scraping**: Apify actors (instagram-post-scraper, instagram-comment-scraper)

## PRD & Epics Created (2026-02-21)
- PRD: `docs/prd/PRD-instagram-campaign.md` (15 FRs, 10 NFRs, 10 CONs)
- EPIC-1: Backend (7 stories) - `docs/stories/epics/EPIC-1-backend.md`
- EPIC-2: Frontend (8 stories) - `docs/stories/epics/EPIC-2-frontend.md`
- EPIC-3: Infra (3 stories) - `docs/stories/epics/EPIC-3-infra.md`
- Total: 18 stories across 3 epics

## Key Decisions
- Polyrepo structure (2 separate repos)
- VADER primary + LLM fallback for sentiment
- APScheduler in-process (no external queue)
- No auth for MVP (internal campaign tool)
- 2 fixed candidates: @charlles.evangelista, @delegadasheila

## AIOS Framework Note
- This project does NOT have .aios-core installed locally
- AIOS templates loaded from global path: ~/Documents/palestras/aios-core/.aios-core/

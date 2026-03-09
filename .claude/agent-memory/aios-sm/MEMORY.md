# SM Agent Memory -- instagram-campaign-api

## Project Context

**Repo:** `/Users/lucascharao/instagram-campaign-api`
**Stack:** FastAPI + Supabase + Apify + APScheduler + vaderSentiment + OpenAI
**Tipo:** Ferramenta interna de analytics de campanha politica

## Docs de Referencia

- PRD: `docs/prd/PRD-instagram-campaign.md`
- Epic 1 (Backend): `docs/stories/epics/EPIC-1-backend.md`
- Epic 2 (Frontend): `docs/stories/epics/EPIC-2-frontend.md`
- Epic 3 (Infra): `docs/stories/epics/EPIC-3-infra.md`
- Architecture: `docs/architecture/architecture.md`
- Schema: `docs/architecture/SCHEMA.md`
- Migrations: `supabase/migrations/001-005`

## Stories Criadas

- `docs/stories/1.1.story.md` -- Setup FastAPI + Supabase client (3pts) -- Draft
- `docs/stories/1.2.story.md` -- Apify post scraping (5pts) -- Draft
- `docs/stories/1.3.story.md` -- Apify comment scraping (5pts) -- Draft
- `docs/stories/1.4.story.md` -- VADER sentiment analysis (3pts) -- Draft
- `docs/stories/1.5.story.md` -- LLM fallback sentiment (5pts) -- Draft
- `docs/stories/1.6.story.md` -- Analytics endpoints (8pts) -- Draft
- `docs/stories/1.7.story.md` -- Scheduler + strategic suggestions (8pts) -- Draft

## Stories do Epic 2 (Frontend) - Criadas em 2026-02-21

- `2.1.story.md` -- Next.js 16 setup + layout shell (3pts) -- Draft
- `2.2.story.md` -- API client + hooks + shared components (5pts) -- Draft
- `2.3.story.md` -- Overview dashboard with metric cards (5pts) -- Draft
- `2.4.story.md` -- Sentiment timeline chart Recharts (5pts) -- Draft
- `2.5.story.md` -- Word cloud (react-d3-cloud) (3pts) -- Draft
- `2.6.story.md` -- Theme analysis bar/pie charts (5pts) -- Draft
- `2.7.story.md` -- Post table + candidate comparison (8pts) -- Draft
- `2.8.story.md` -- Strategic insights view (3pts) -- Draft

## Convencoes Frontend (instagram-campaign-web)

- Stack: Next.js 16 + Tailwind 4 + shadcn/ui + Recharts + pnpm
- App Router + src/ directory + TypeScript
- Tailwind 4: CSS-first (@import "tailwindcss"), sem tailwind.config.js
- CandidateFilter: URL search params (nao React Context)
- Date picker: native input[type=date] para MVP
- Word cloud: react-d3-cloud (NAO react-wordcloud - conflito d3 v7)
- Sparkline: 2 pontos do trend object (previous_avg + recent_avg)
- Candidatos: charlles.evangelista (azul --color-candidate-a), delegadasheila (rose --color-candidate-b)

## Convencoes do Projeto

- Sem ORM -- usar supabase-py SDK diretamente (CON-003)
- Funcoes PL/pgSQL em `supabase/migrations/004_create_functions.sql` -- usar via `supabase.rpc()`
- Perfis monitorados: `charlles.evangelista` e `delegadasheila` (fixos, CON-002)
- VADER thresholds: positive >= 0.05, negative <= -0.05 (constantes em `app/core/constants.py`)
- LLM fallback: apenas comentarios ambiguos com len > 20 chars
- Actor IDs: `apify/instagram-post-scraper`, `apify/instagram-comment-scraper`

## Estrutura de Pastas (architecture.md Secao 2.1)

```
app/
  main.py, core/, db/, models/, routers/, services/, scheduler/
tests/
  conftest.py, test_scraping.py, test_sentiment.py, test_analytics.py,
  test_themes.py, test_pipeline.py
supabase/migrations/  (001-005 existentes)
```

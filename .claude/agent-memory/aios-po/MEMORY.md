# PO Agent Memory - instagram-campaign-api

## Project Structure
- **PRD:** `/Users/lucascharao/instagram-campaign-api/docs/prd/PRD-instagram-campaign.md`
- **Architecture:** `/Users/lucascharao/instagram-campaign-api/docs/architecture/architecture.md`
- **SCHEMA.md:** `/Users/lucascharao/instagram-campaign-api/docs/architecture/SCHEMA.md`
- **Epics:** `/Users/lucascharao/instagram-campaign-api/docs/stories/epics/`
- **Stories:** `/Users/lucascharao/instagram-campaign-api/docs/stories/`
- **Migrations:** `/Users/lucascharao/instagram-campaign-api/supabase/migrations/001-005`
- No `.aios-core` directory in this project (uses global AIOS installation)
- No `.aios/gotchas.json` in this project

## Validation History
- Story 1.1: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 1.2: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 1.3: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 1.4: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 1.5: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 1.6: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 1.7: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 2.1: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 2.2: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation. Also noted Jest config typo (setupFilesAfterFramework -> setupFilesAfterSetup).
- Story 2.3: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 2.4: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation.
- Story 2.5: GO 9/10 (2026-02-21). Missing Risks section was only failure; added during validation. Noted library choice deviation (react-d3-cloud vs PRD suggestions) -- justified by AUTO-DECISION.
- Story 2.6: GO 9/10 (2026-02-22). Missing Risks section was only failure; added during validation.
- Story 2.7: GO 9/10 (2026-02-22). Missing Risks section was only failure; added during validation. Largest story in Epic 2 (8 points, 12 ACs, 2 pages).
- Story 2.8: GO 9/10 (2026-02-22). Missing Risks section was only failure; added during validation. Final story of Epic 2, includes pnpm build as epic completion gate.

## Recurring Pattern
- All stories from River (SM) across Epic 1 (1.1-1.7) and Epic 2 (2.1-2.8) are consistently missing a "## Risks" section. Pattern confirmed across 15 validations. All other 9 checklist items pass consistently -- story quality is high. This needs to be communicated as feedback for future story creation.

## Epic 2 Completion
- All 8 stories (2.1-2.8) validated GO. Epic 2 is fully validated and Ready for implementation.
- Story 2.8 (final story) includes T3.3 `pnpm build` as the Epic 2 completion gate.

## Schema Divergence Pattern
The SCHEMA.md has a richer schema (7 tables including strategic_insights, extra columns like raw_data, shortcode, is_sponsored, etc.) than what the Epic 1 story summaries describe. Stories should reference SCHEMA.md as source of truth for column definitions.

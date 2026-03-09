# Dev Agent Memory

## Next.js 16 Patterns
- `useSearchParams()` requires a Suspense boundary in Next.js 16. Pages that use it need to be split into: Server Component page wrapper (with Suspense) + Client Component content (with the hooks). See `overview/page.tsx` + `overview/overview-content.tsx` pattern.
- `next/dynamic` with `{ ssr: false }` is needed for browser-only libs like react-d3-cloud.

## React Compiler Lint Rules (CRITICAL)
- This project uses React Compiler ESLint plugin with strict rules.
- **NO `setState` inside `useEffect`** -- `react-hooks/set-state-in-effect` error. Derive state from props/data or use event handlers.
- **NO `useCallback` with empty deps** when the callback uses state setters -- `react-hooks/preserve-manual-memoization` error. React Compiler infers deps automatically.
- **NO `useRef.current` access during render** -- `react-hooks/refs` error. Refs can only be read in event handlers or effects.
- **Pattern for "load more" pagination**: Use `useApiData` for first page (offset=0), then use `fetchXxx()` directly in the "load more" click handler to append to state via `setExtraPosts(prev => [...prev, ...result])`. Reset `extraPosts` in sort/filter handlers.
- **Recharts PieLabelRenderProps**: Custom label functions must use `PieLabelRenderProps` type from recharts, with `Number()` coercion for optional numeric fields.

## Project Structure (instagram-campaign-web)
- Hooks: `src/hooks/use-*.ts` using `useApiData` base hook
- Shared components: `src/components/shared/` (empty-state, error-message, loading-skeleton)
- Dashboard components: `src/components/dashboard/` (metric-card, sentiment-badge, sentiment-bar, summary-row, trend-indicator, suggestion-card)
- Chart components: `src/components/charts/` (sentiment-line, word-cloud, theme-bar, theme-pie, sparkline)
- UI primitives: `src/components/ui/` (shadcn components)
- Utils: `src/lib/utils.ts` has `cn`, `formatDate`, `formatDateShort`, `formatDateMedium`, `getCandidateId`, `formatThemeLabel`
- Constants: `src/lib/constants.ts` has candidate usernames, colors, nav tabs, CandidateFilter type

## Key Utilities
- `getCandidateId(filter, candidates)` resolves CandidateFilter URL param to UUID. Reusable across all pages needing candidate-specific API calls.
- `formatThemeLabel(theme)` maps theme_category enum values to human-readable Portuguese labels.
- `react-d3-cloud` has peer dep warnings with React 19 but works fine at runtime.
- Recharts v3 is installed and works with React 19.

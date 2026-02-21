# Epic 2: Frontend (Next.js Dashboard)

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-2 |
| **Title** | Frontend Dashboard -- Visualizations & Strategic Insights |
| **Status** | Draft |
| **Repository** | instagram-campaign-web |
| **Stories** | 8 |
| **PRD Reference** | `docs/prd/PRD-instagram-campaign.md` |
| **Depends On** | EPIC-1 (API must be functional) |

---

## Goal

Build a responsive Next.js dashboard that visualizes all analytics data from the backend API, enabling campaign strategists to compare candidates side by side, track sentiment over time, identify recurring themes in public discourse, and act on AI-generated strategic suggestions. Every view in the dashboard maps to a specific API endpoint from Epic 1, ensuring the frontend is purely a presentation layer with no business logic.

---

## Scope

### In Scope
- Next.js 16 project scaffolding with Tailwind CSS and shadcn/ui
- Tab-based navigation layout with responsive design (desktop primary)
- Typed API client with data fetching hooks for all Epic 1 endpoints
- Overview dashboard with side-by-side candidate metric cards
- Sentiment timeline line chart (Recharts) with date range filtering
- Word cloud visualization with candidate filter toggle
- Theme analysis bar/pie charts per candidate
- Post comparison sortable table
- Candidate comparison dedicated view
- Strategic insights view with AI suggestions display
- Loading states, error states, and empty states for all views
- Basic WCAG AA compliance (contrast, keyboard nav, alt text)

### Out of Scope
- User authentication / login page
- Real-time WebSocket updates
- Dark mode
- Mobile-optimized layouts (tablet is minimum breakpoint)
- Export functionality (PDF/CSV)
- Deployment to Vercel (Epic 3)

---

## Dependencies

- Epic 1 complete (all API endpoints functional)
- shadcn/ui component library
- Recharts for charts
- React word cloud library (e.g., `react-wordcloud` or `@visx/wordcloud`)

---

## Stories

---

### Story 2.1: Project Setup & Layout Shell

**As a** frontend developer,
**I want** a properly scaffolded Next.js project with Tailwind, shadcn/ui, and a consistent layout shell,
**so that** all subsequent stories have a solid foundation with navigation and styling in place.

**PRD References**: CON-004, CON-007

#### Acceptance Criteria

1. Next.js 16 project is initialized in the `instagram-campaign-web` repository with TypeScript enabled and App Router.
2. Tailwind CSS is configured with a neutral color palette (slate/blue as default). Colors for "Candidate A" and "Candidate B" are defined as CSS variables for consistent use across charts and cards.
3. shadcn/ui is installed and configured. At minimum: Button, Card, Tabs, Badge, Skeleton, and Table components are available.
4. A root layout (`app/layout.tsx`) renders a header with the application title ("Instagram Campaign Analytics"), a tab-based navigation bar (Overview, Sentiment, Words, Themes, Posts, Comparison, Insights), and a main content area.
5. Each tab route has a placeholder page (`app/overview/page.tsx`, `app/sentiment/page.tsx`, etc.) that renders a heading and an "Under Construction" message.
6. A reusable `CandidateFilter` component provides a toggle/select to filter views by candidate (All, Candidate A, Candidate B). It is placed in the layout header area.
7. Environment variable `NEXT_PUBLIC_API_URL` is defined in `.env.example` pointing to the backend API base URL.
8. The project builds without errors (`npm run build` succeeds).
9. Basic responsive behavior: layout adjusts to viewport width >= 768px (tablet) and >= 1024px (desktop).

#### Dev Notes
- Use Next.js App Router (not Pages Router).
- Tab navigation uses Next.js `Link` components with active state styling.
- CandidateFilter state can use URL search params or React context for simplicity.

---

### Story 2.2: API Client & Data Fetching

**As a** frontend developer,
**I want** a typed API client with reusable data fetching hooks for every backend endpoint,
**so that** all dashboard views can fetch data consistently with proper loading and error handling.

**PRD References**: FR-006 through FR-012, NFR-001

#### Acceptance Criteria

1. An API client module (`lib/api.ts`) exports typed functions for every Epic 1 endpoint:
   - `fetchOverview() -> OverviewData`
   - `fetchSentimentTimeline(candidateId, startDate?, endDate?) -> TimelineData[]`
   - `fetchWordCloud(candidateId?) -> WordCloudData[]`
   - `fetchThemes(candidateId?) -> ThemeData[]`
   - `fetchPosts(candidateId?, sortBy?, order?) -> PostData[]`
   - `fetchComparison() -> ComparisonData`
   - `fetchSuggestions(candidateId?) -> Suggestion[]`
   - `triggerScraping() -> ScrapingRunStatus`
   - `fetchHealth() -> HealthStatus`
2. All response types are defined as TypeScript interfaces in `lib/types.ts`, matching the Pydantic response schemas from Epic 1.
3. Custom hooks (`hooks/use-overview.ts`, `hooks/use-sentiment-timeline.ts`, etc.) wrap each API function with:
   - Loading state (boolean)
   - Error state (Error | null)
   - Data state (typed response | null)
   - Refetch function
4. API calls use `fetch` with the `NEXT_PUBLIC_API_URL` base URL. No external state management library (no Redux, no Zustand).
5. All hooks handle network errors gracefully and expose them through the error state.
6. A shared `ErrorMessage` component displays user-friendly error messages when API calls fail.
7. A shared `LoadingSkeleton` component displays shimmer placeholders during data loading.
8. Unit tests verify type correctness and error handling for at least 3 hooks.

#### Dev Notes
- Consider using SWR or React Query if the project benefits from caching/revalidation, but keep it simple -- plain fetch + useState/useEffect is acceptable for MVP.
- All type definitions must match the API Pydantic schemas exactly.
- Depends on Story 2.1 (project scaffolding).

---

### Story 2.3: Overview Dashboard

**As a** campaign strategist,
**I want** a dashboard overview showing key metrics for both candidates side by side,
**so that** I can quickly assess the current state of engagement and sentiment at a glance.

**PRD References**: FR-006, FR-011

#### Acceptance Criteria

1. The `/overview` page displays metric cards for each candidate arranged side by side (2-column layout on desktop, stacked on tablet).
2. Each candidate card shows: candidate name/username, total posts scraped, total comments, average sentiment score (with color-coded badge: green positive, red negative, gray neutral), sentiment distribution (positive/negative/neutral counts with percentage bars), and total engagement (likes + comments).
3. A summary row above the cards shows aggregate totals: total comments analyzed, overall average sentiment, and the last scraping run timestamp.
4. All data is fetched from `GET /api/v1/analytics/overview` using the `useOverview` hook.
5. Loading state renders shadcn Skeleton components in the shape of the metric cards.
6. Error state renders the shared `ErrorMessage` component.
7. Empty state (no data yet) renders a message suggesting the user trigger a scraping run, with a button that calls `POST /api/v1/scraping/run`.
8. Metric values update when data changes (manual page refresh is acceptable for MVP -- no auto-refresh).

#### Dev Notes
- Use shadcn/ui Card components for metric cards.
- Color-code sentiment: define thresholds (>= 0.05 green, <= -0.05 red, else gray).
- Depends on Story 2.2 (API client and hooks).

---

### Story 2.4: Sentiment Timeline Chart

**As a** campaign strategist,
**I want** a line chart showing how sentiment evolves over time for each candidate,
**so that** I can identify trends and correlate sentiment shifts with specific events or posts.

**PRD References**: FR-007

#### Acceptance Criteria

1. The `/sentiment` page displays a Recharts `LineChart` with:
   - X-axis: post timestamps (formatted as "DD/MM" or "DD/MM/YY").
   - Y-axis: average sentiment compound score per post (range -1.0 to 1.0).
   - One line per candidate, colored according to the candidate color variables from Story 2.1.
   - Tooltip showing: date, candidate name, sentiment score, post caption (truncated to 60 chars).
2. A date range picker allows the user to filter the timeline to a specific period. Default: last 30 days.
3. The `CandidateFilter` from Story 2.1 can toggle between showing both candidates, only Candidate A, or only Candidate B.
4. Data is fetched from `GET /api/v1/analytics/sentiment-timeline` using the `useSentimentTimeline` hook with candidate and date parameters.
5. A horizontal reference line at y=0 visually separates positive from negative territory.
6. Loading state shows a skeleton in the shape of a chart area.
7. Empty state (no posts in date range) shows a descriptive message.
8. Chart is responsive: adjusts width to container on resize.

#### Dev Notes
- Use Recharts `ResponsiveContainer`, `LineChart`, `Line`, `XAxis`, `YAxis`, `Tooltip`, `Legend`, `ReferenceLine`.
- Date range picker: use a shadcn/ui date picker or two input fields with type="date" for MVP simplicity.
- Depends on Story 2.2 (API client).

---

### Story 2.5: Word Cloud Visualization

**As a** campaign strategist,
**I want** a word cloud showing the most frequent words in comments,
**so that** I can quickly see what topics the public is discussing about each candidate.

**PRD References**: FR-008

#### Acceptance Criteria

1. The `/words` page displays a word cloud visualization where word size corresponds to frequency.
2. The `CandidateFilter` toggles the word cloud between: all comments, Candidate A comments only, Candidate B comments only.
3. Data is fetched from `GET /api/v1/analytics/wordcloud` using the `useWordCloud` hook with the selected candidate filter.
4. The word cloud renders at least 50 words (or all available words if fewer than 50).
5. A legend or subtitle indicates the current filter selection and total number of unique words.
6. Clicking a word (optional for MVP) shows a tooltip with the exact count.
7. Loading state shows a skeleton placeholder.
8. Empty state shows a descriptive message if no word data is available.
9. Color palette for words uses a gradient or categorical scheme that is visually distinct from the candidate colors.

#### Dev Notes
- Library options: `react-wordcloud`, `@visx/wordcloud`, or a lightweight alternative. Choose the one with the simplest API.
- Word cloud libraries can be heavy; consider dynamic import (`next/dynamic` with SSR disabled) for performance.
- Depends on Story 2.2 (API client).

---

### Story 2.6: Theme Analysis View

**As a** campaign strategist,
**I want** to see how comments are distributed across themes (health, security, education, etc.) for each candidate,
**so that** I can identify which topics generate the most engagement and where to focus campaign messaging.

**PRD References**: FR-009

#### Acceptance Criteria

1. The `/themes` page displays theme distribution for each candidate using bar charts (Recharts `BarChart`).
2. The default view shows a grouped bar chart with themes on the X-axis and comment count on the Y-axis, with one bar per candidate per theme.
3. An alternative view (toggle button) shows a pie chart per candidate displaying theme proportions.
4. The `CandidateFilter` adjusts the view: both candidates (grouped bars), or single candidate (single bar series or single pie).
5. Data is fetched from `GET /api/v1/analytics/themes` using the `useThemes` hook.
6. Each theme bar/slice is labeled with the theme name and count/percentage.
7. Themes are sorted by total count descending (most discussed theme first).
8. Loading, error, and empty states follow the same patterns established in previous stories.

#### Dev Notes
- Use Recharts `BarChart`, `Bar`, `PieChart`, `Pie`, `Cell` for the chart variants.
- Theme names from the API (saude, seguranca, etc.) should be displayed with proper Portuguese formatting (Saude, Seguranca, Educacao, etc.).
- Depends on Story 2.2 (API client).

---

### Story 2.7: Post & Candidate Comparison

**As a** campaign strategist,
**I want** to see a ranked list of posts by engagement metrics and a dedicated candidate comparison view,
**so that** I can identify which content performs best and how candidates compare head to head.

**PRD References**: FR-010, FR-011

#### Acceptance Criteria

1. The `/posts` page displays a sortable table of posts with columns: Candidate, Date, Caption (truncated), Likes, Comments, Positive %, Negative %, Sentiment Score.
2. Each column header is clickable to sort ascending/descending. Default sort: by comment count descending.
3. The `CandidateFilter` filters the table to show one or both candidates.
4. Data is fetched from `GET /api/v1/analytics/posts` using the `usePosts` hook with sort and filter parameters.
5. The `/comparison` page displays a dedicated side-by-side comparison view with:
   - Metric cards: total posts, total comments, average sentiment, total engagement for each candidate.
   - Top 3 themes per candidate.
   - Sentiment trend direction: "Improving" (up arrow, green) or "Declining" (down arrow, red) based on the API's trend calculation.
   - A mini sentiment timeline chart (last 10 data points per candidate) for quick visual comparison.
6. Comparison data is fetched from `GET /api/v1/analytics/comparison` using the `useComparison` hook.
7. The post table supports pagination or a "Load More" button if results exceed 20 rows.
8. Loading, error, and empty states follow established patterns.

#### Dev Notes
- Use shadcn/ui Table component for the post table.
- Trend direction visual: simple arrow icon + text, color-coded.
- Mini chart: a simplified Recharts LineChart without axes labels (sparkline style).
- Depends on Story 2.2 (API client).

---

### Story 2.8: Strategic Insights View

**As a** campaign strategist,
**I want** to see AI-generated strategic suggestions with supporting data,
**so that** I can make informed decisions about campaign messaging and positioning.

**PRD References**: FR-012

#### Acceptance Criteria

1. The `/insights` page displays 3-5 AI-generated strategic suggestions.
2. Each suggestion is rendered as a card with: title (bold), description (paragraph), supporting data point (highlighted metric or comparison), and priority badge (High = red, Medium = yellow, Low = green).
3. A "Refresh Suggestions" button triggers `POST /api/v1/analytics/suggestions` to generate new suggestions based on the latest data. The button shows a loading spinner during generation.
4. The `CandidateFilter` can optionally scope suggestions to a specific candidate (passed as `candidate_id` parameter).
5. Suggestions are fetched on page load from the same endpoint (GET variant or POST with defaults).
6. A disclaimer text is displayed below the suggestions: "Suggestions are AI-generated based on available data and should be validated by the campaign team."
7. Loading state shows skeleton cards. Error state shows the shared error component. Empty state explains that data collection may need to run first.
8. Each suggestion card has a subtle border on the left side colored by priority for quick visual scanning.

#### Dev Notes
- Use shadcn/ui Card with custom left-border styling for priority indication.
- The "Refresh" action may take several seconds (LLM call); ensure good loading UX.
- This is the final dashboard view -- ensure navigation tab order matches PRD section 11.3.
- Depends on Story 2.2 (API client).

---

## Definition of Done (Epic Level)

- [ ] All 8 stories implemented and rendering correctly.
- [ ] All views fetch data from the API and handle loading/error/empty states.
- [ ] Tab navigation works correctly between all 7 views.
- [ ] CandidateFilter component filters data across all applicable views.
- [ ] Charts render responsively on desktop (>= 1024px) and tablet (>= 768px) viewports.
- [ ] No TypeScript errors (`npm run build` succeeds).
- [ ] Basic WCAG AA: sufficient color contrast, keyboard-navigable tabs, alt text on chart containers.
- [ ] Component tests pass for metric cards, table, and at least one chart view.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-02-21 | 1.0.0 | Initial epic creation | Bob (PM Agent) |

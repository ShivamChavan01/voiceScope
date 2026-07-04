# VoiceScope Frontend — Implementation Plan

## Overview

Build a 2-page dark Claude-aesthetic dashboard for VoiceScope using Next.js 16 + Tailwind v4 + Recharts. The frontend connects to the existing FastAPI backend at `/api/v1/`.

**Design source:** `DESIGN-PROMPT.md` (super dark Claude aesthetic, flat sidebar, serif headlines, monospace metrics)

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | Next.js 16 (App Router) | Already scaffolded, React 19 |
| Styling | Tailwind CSS v4 | Already configured, CSS-first |
| Charts | Recharts | React-native, composable, dark-theme friendly |
| Icons | Lucide React | Lightweight, consistent, matches DESIGN-PROMPT.md |
| Fonts | Geist (sans) + Geist Mono (mono) + Georgia (serif) | Already in layout.tsx, add serif via CSS |
| State | React hooks + SWR | Lightweight, no Redux needed for 2 pages |
| Data | fetch() to backend API | Direct, no SDK needed |

**shadcn/ui** — use as base, customize heavily for dark Claude aesthetic. shadcn gives us accessible primitives (Button, Card, Badge, Input) with proper ARIA. We override styles via Tailwind classes to match DESIGN-PROMPT.md.

---

## Architecture

```
src/
├── app/
│   ├── layout.tsx          ← Root layout (sidebar + content shell)
│   ├── page.tsx            ← Dashboard Home (redirect or render)
│   ├── dashboard/
│   │   └── page.tsx        ← Dashboard Home
│   ├── analysis/
│   │   └── page.tsx        ← Call Analysis
│   └── globals.css         ← Design tokens + Tailwind theme
├── components/
│   ├── sidebar.tsx         ← Flat sidebar navigation
│   ├── theme-toggle.tsx    ← Sun/Moon toggle
│   ├── metric-card.tsx     ← Hero + secondary metric cards
│   ├── section-divider.tsx ← Serif italic section headers
│   ├── status-badge.tsx    ← Colored status badges
│   ├── progress-bar.tsx    ← Layer score progress bars
│   ├── layer-breakdown.tsx ← Full layer breakdown component
│   ├── outcome-chart.tsx   ← Donut chart for outcomes
│   ├── recent-calls.tsx    ← Recent calls table
│   ├── upload-form.tsx     ← Audio upload / run ID input
│   ├── transcript-box.tsx  ← Transcript display
│   └── call-result.tsx     ← Analysis result display
├── lib/
│   ├── api.ts              ← Backend API client
│   ├── types.ts            ← TypeScript interfaces
│   └── utils.ts            ← cn() helper, formatters
└── hooks/
    └── use-api.ts          ← SWR hooks for data fetching
```

---

## Step-by-Step Plan

### Step 1: Install Dependencies + shadcn/ui Setup

**Files:** `package.json`, `src/app/globals.css`, `src/lib/utils.ts`, `components.json`

```bash
cd frontend
npm install
npx shadcn@latest init -d
npm install recharts lucide-react swr
npm install -D @types/node
```

**shadcn init** will:
- Create `components.json` (config)
- Create `src/lib/utils.ts` (cn() helper)
- Set up CSS variables in `globals.css`
- Configure Tailwind for shadcn

**Then override globals.css with our dark tokens:**
```css
@import "tailwindcss";

@theme inline {
  --color-background: #0d0d0d;
  --color-foreground: #f0ebe3;
  --color-card: #1a1a1a;
  --color-card-foreground: #f0ebe3;
  --color-popover: #222222;
  --color-popover-foreground: #f0ebe3;
  --color-primary: #818cf8;
  --color-primary-foreground: #0d0d0d;
  --color-secondary: #1a1a1a;
  --color-secondary-foreground: #c4bfb6;
  --color-muted: #1a1a1a;
  --color-muted-foreground: #6b6760;
  --color-accent: #252525;
  --color-accent-foreground: #f0ebe3;
  --color-destructive: #f87171;
  --color-destructive-foreground: #0d0d0d;
  --color-border: #2a2825;
  --color-input: #2a2825;
  --color-ring: #818cf8;
  --color-success: #4ade80;
  --color-warning: #fbbf24;
  --color-surface-sidebar: #111111;
  --color-surface-recessed: #141414;
  --color-surface-hover: #252525;
  --radius: 0.75rem;
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}
```

**shadcn components to install:**
```bash
npx shadcn@latest add button card badge input separator table tooltip
```

### Step 2: Root Layout + Sidebar Shell

**Files:** `src/app/layout.tsx`, `src/components/sidebar.tsx`, `src/components/theme-toggle.tsx`

**layout.tsx** — Replace boilerplate with:
- Import Geist + Geist Mono fonts (already done)
- Add Georgia via CSS `font-family` fallback
- Wrap children in sidebar + content layout
- Set `<body className="bg-canvas text-text-body">`

**sidebar.tsx** — Flat sidebar:
- Width: 260px, fixed, full height
- Background: `bg-surface-sidebar`
- Logo: Lucide `Mic` icon + "VoiceScope" serif italic
- Nav items: flat, no border-radius, `border-l-2` on active
- Nav items: Dashboard, Analysis, Monitoring (ghost), Self-Improve (ghost), QA (ghost)
- Bottom: Settings + Theme toggle
- Active state tracked via `usePathname()`

**theme-toggle.tsx** — Sun/Moon icon button

### Step 3: API Client + Types

**Files:** `src/lib/api.ts`, `src/lib/types.ts`, `src/hooks/use-api.ts`

**types.ts:**
```ts
interface DashboardStats {
  total_calls: number;
  hallucination_rate: number;
  avg_cost: number;
  total_tokens: number;
  avg_duration: number;
  outcome_split: { resolved: number; unresolved: number; escalated: number };
  recent_calls: CallSummary[];
}

interface CallSummary {
  run_id: string;
  intent: string;
  truth_score: number;
  status: "passed" | "warning" | "failed";
}

interface AnalysisResult {
  run_id: string;
  intent: string;
  truth_score: number;
  confidence: string;
  transcript: TranscriptLine[];
  layers: LayerResult[];
  sentiment: string;
  outcome: string;
  hallucination_detected: boolean;
}

interface LayerResult {
  name: string;
  score: number;
  weight: number;
}
```

**api.ts:**
```ts
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchDashboard(): Promise<DashboardStats> { ... }
export async function fetchAnalysis(runId: string): Promise<AnalysisResult> { ... }
export async function uploadAudio(file: File): Promise<AnalysisResult> { ... }
```

**use-api.ts** — SWR hooks:
```ts
import useSWR from "swr";
export function useDashboard() { return useSWR("/api/v1/dashboard", fetcher); }
export function useAnalysis(runId: string) { return useSWR(runId ? `/api/v1/analysis/${runId}` : null, fetcher); }
```

### Step 4: Shared Components (shadcn + custom)

**Files:** `src/components/metric-card.tsx`, `section-divider.tsx`, `status-badge.tsx`, `progress-bar.tsx`

**metric-card.tsx** — wraps shadcn `Card`:
- Import `Card, CardContent, CardHeader, CardTitle` from `@/components/ui/card`
- Override card styles: `bg-[#1a1a1a] border-[#2a2825]`
- Props: `title`, `value`, `trend?`, `trendDirection?`, `variant: "hero" | "secondary"`
- Hero: 64px monospace value, chart slot
- Secondary: 28px monospace value
- Trend: green for up, red for down

**section-divider.tsx** — wraps shadcn `Separator`:
- Import `Separator` from `@/components/ui/separator`
- Serif italic text centered between thin lines
- "— Section Name —" format

**status-badge.tsx** — wraps shadcn `Badge`:
- Import `Badge` from `@/components/ui/badge`
- Props: `status: "passed" | "warning" | "failed"`, `label`
- Color-coded: green/yellow/red background + text

**progress-bar.tsx** — custom (no shadcn equivalent):
- Props: `value` (0-1), `height?: "hero" | "inline"`
- Fill: `bg-[#818cf8]`, track: `bg-[#252525]`

### Step 5: Dashboard Page

**Files:** `src/app/dashboard/page.tsx`, `src/components/outcome-chart.tsx`, `src/components/recent-calls.tsx`

**dashboard/page.tsx:**
- Fetch data via `useDashboard()`
- Layout: hero row (2 cards) + secondary row (3 cards) + section divider + outcome + recent calls
- Loading state: skeleton loaders
- Empty state: "No calls yet" message

**outcome-chart.tsx:**
- Recharts `PieChart` with dark theme
- Colors: `#4ade80` (resolved), `#fbbf24` (unresolved), `#f87171` (escalated)
- Legend below chart

**recent-calls.tsx** — wraps shadcn `Table`:
- Import `Table, TableBody, TableCell, TableHead, TableHeader, TableRow` from `@/components/ui/table`
- Columns: Run ID, Intent, Score, Status
- Monospace for run IDs
- Status badges for pass/warning/fail
- Link to `/analysis?id=<run_id>`

### Step 6: Analysis Page

**Files:** `src/app/analysis/page.tsx`, `src/components/upload-form.tsx`, `src/components/layer-breakdown.tsx`, `src/components/transcript-box.tsx`, `src/components/call-result.tsx`

**analysis/page.tsx:**
- Split view: upload form left (1/3), results right (2/3)
- Read `?id=` query param for pre-filled analysis
- Upload form: drag-drop audio or enter run ID
- Results: intent headline, sentiment badges, truth score, layer breakdown, transcript

**upload-form.tsx** — wraps shadcn `Input` + `Button`:
- Import `Input` from `@/components/ui/input`
- Import `Button` from `@/components/ui/button`
- Drag-drop zone for audio files
- Text input for run ID
- "Analyze" button (primary, `bg-[#818cf8]`)
- Loading state during analysis

**layer-breakdown.tsx:**
- List of layers with color strips (green/yellow/red based on score)
- Progress bar per layer
- Score in monospace

**transcript-box.tsx:**
- Recessed background (`bg-surface-recessed`)
- Speaker labels in bold
- Line height 1.7 for readability

**call-result.tsx:**
- Intent headline (serif italic, 48px)
- Sentiment + outcome + hallucination badges
- Truth score (56px monospace)
- Confidence label
- Overall progress bar

### Step 7: Polish + Responsive

**Files:** All components

- Add hover states to all interactive elements
- Add focus rings for keyboard navigation
- Add page transition animations (fade-in)
- Test responsive: sidebar collapses to icons on mobile
- Add loading skeletons for all data-fetching states
- Add empty states for no-data scenarios

---

## File Creation Order

| Order | File | What |
|-------|------|------|
| 1 | `npx shadcn@latest init -d` | shadcn setup |
| 2 | `npx shadcn@latest add button card badge input separator table tooltip` | shadcn components |
| 3 | `src/app/globals.css` | Override with dark tokens |
| 4 | `src/components/sidebar.tsx` | Sidebar navigation |
| 5 | `src/components/theme-toggle.tsx` | Theme toggle |
| 6 | `src/app/layout.tsx` | Root layout with sidebar |
| 7 | `src/lib/types.ts` | TypeScript interfaces |
| 8 | `src/lib/api.ts` | API client |
| 9 | `src/hooks/use-api.ts` | SWR hooks |
| 10 | `src/components/metric-card.tsx` | Metric cards (wraps shadcn Card) |
| 11 | `src/components/section-divider.tsx` | Section dividers (wraps shadcn Separator) |
| 12 | `src/components/status-badge.tsx` | Status badges (wraps shadcn Badge) |
| 13 | `src/components/progress-bar.tsx` | Progress bars |
| 14 | `src/components/outcome-chart.tsx` | Donut chart |
| 15 | `src/components/recent-calls.tsx` | Recent calls table (wraps shadcn Table) |
| 16 | `src/app/dashboard/page.tsx` | Dashboard page |
| 17 | `src/components/upload-form.tsx` | Upload form (wraps shadcn Input + Button) |
| 18 | `src/components/transcript-box.tsx` | Transcript display |
| 19 | `src/components/layer-breakdown.tsx` | Layer breakdown |
| 20 | `src/components/call-result.tsx` | Call result display |
| 21 | `src/app/analysis/page.tsx` | Analysis page |
| 22 | Polish all components | Hover, focus, responsive |

---

## API Endpoints Used

| Frontend | Backend | Method |
|----------|---------|--------|
| Dashboard stats | `GET /api/v1/dashboard` | May need to create |
| Recent calls | `GET /api/v1/calls` | May need to create |
| Run analysis | `POST /api/v1/analyze` | Exists |
| Stream analysis | `POST /api/v1/analyze/stream` | Exists |
| Get analysis | `GET /api/v1/analysis/{run_id}` | May need to create |
| Health check | `GET /api/v1/health` | Exists |

**Note:** Some endpoints may not exist yet. The plan includes creating mock data for development and wiring to real API when available.

---

## Estimated Time

| Step | Time |
|------|------|
| Step 1: Dependencies + tokens | 5 min |
| Step 2: Layout + sidebar | 15 min |
| Step 3: API client + types | 10 min |
| Step 4: Shared components | 15 min |
| Step 5: Dashboard page | 20 min |
| Step 6: Analysis page | 20 min |
| Step 7: Polish | 15 min |
| **Total** | **~100 min** |

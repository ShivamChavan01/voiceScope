# VoiceScope Frontend — Design System

## Product Context

VoiceScope is a voice AI observability tool that sits behind another AI. It's not a product someone lives in all day. The frontend's job: show what happened, show if something's wrong, let a human configure the boring bits.

**3 screens:**
1. **Overview** — health metrics, truth score trend, active alerts, recent runs
2. **Runs** — list of analyzed calls, click into a run for full report + 7-layer harness breakdown + transcript
3. **Settings** — providers/API keys, guardrails, alert rules, extraction schemas, QA cohorts (all tabs on one page)

---

## Design Philosophy

**Minimal embedded dashboard.** Not a standalone product. Not a SaaS landing page. A dark, quiet tool that sits in a sidebar or tab and does its job.

**Inspiration:** Claude.ai dark mode, Linear, Vercel dashboard, Raycast. Clean type, warm dark palette, no visual noise.

---

## Color System

### Dark Mode (Default — only mode)

| Token | Hex | Usage |
|-------|-----|-------|
| `canvas` | `#0a0a0a` | Page background |
| `surface` | `#111111` | Cards, sidebar |
| `surface-elevated` | `#1a1a1a` | Dropdowns, modals, hover states |
| `surface-recessed` | `#0f0f0f` | Code blocks, transcript boxes |
| `border` | `#222222` | Card borders, dividers |
| `border-subtle` | `#1a1a1a` | Internal dividers |
| `text-primary` | `#ededed` | Headlines, primary text |
| `text-secondary` | `#a1a1a1` | Body copy |
| `text-muted` | `#666666` | Captions, timestamps |
| `accent` | `#818cf8` | Buttons, active states, links |
| `accent-hover` | `#a5b4fc` | Accent hover |
| `accent-muted` | `rgba(129,140,248,0.12)` | Hover tints |
| `success` | `#4ade80` | Passed, healthy |
| `warning` | `#fbbf24` | Warning, medium |
| `error` | `#f87171` | Failed, critical |

### No light mode. Dark only.

---

## Typography

| Role | Font | Size | Weight | Color |
|------|------|------|--------|-------|
| Page title | Inter | 24px | 600 | `#ededed` |
| Section title | Inter | 16px | 500 | `#ededed` |
| Card title | Inter | 13px | 500 | `#a1a1a1` (uppercase, tracking 0.5px) |
| Body | Inter | 14px | 400 | `#a1a1a1` |
| Caption | Inter | 12px | 400 | `#666666` |
| Metric (hero) | JetBrains Mono | 48px | 500 | `#ededed` |
| Metric (card) | JetBrains Mono | 24px | 500 | `#ededed` |
| Metric (small) | JetBrains Mono | 16px | 400 | `#a1a1a1` |
| Code/transcript | JetBrains Mono | 13px | 400 | `#a1a1a1` |

---

## Spacing Scale

| Token | Value |
|-------|-------|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-10` | 40px |
| `--space-12` | 48px |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 6px | Badges, small elements |
| `--radius-md` | 8px | Cards, inputs |
| `--radius-lg` | 12px | Modals, large cards |

---

## Shadows

None. Depth through background color shifts only.

---

## Components

### Card
- Background: `#111111`
- Border: `1px solid #222222`
- Border-radius: `8px`
- Padding: `20px`
- No shadow

### Button (Primary)
- Background: `#818cf8`
- Text: `#0a0a0a`
- Border-radius: `8px`
- Padding: `8px 16px`
- Font: 14px, weight 500
- Hover: `#a5b4fc`

### Button (Secondary)
- Background: transparent
- Border: `1px solid #222222`
- Text: `#a1a1a1`
- Border-radius: `8px`
- Padding: `8px 16px`
- Hover: `#1a1a1a`

### Button (Ghost)
- Background: transparent
- Text: `#818cf8`
- No border
- Padding: `8px 16px`
- Hover: `rgba(129,140,248,0.12)`

### Input
- Background: `#0f0f0f`
- Border: `1px solid #222222`
- Border-radius: `8px`
- Padding: `8px 12px`
- Text: `#ededed`
- Placeholder: `#666666`
- Focus: `border-color: #818cf8`

### Badge
- Background: status color at 12% opacity
- Text: status color
- Border-radius: `6px`
- Padding: `2px 8px`
- Font: 12px, weight 500

### Table
- Header: `#111111` background, `#666666` text, uppercase, 12px
- Row: transparent, hover `#111111`
- Border-bottom: `1px solid #222222`
- Cell padding: `12px 16px`

### Progress Bar
- Height: 6px
- Border-radius: 3px
- Fill: `#818cf8`
- Track: `#1a1a1a`

---

## Layout

### Sidebar (260px fixed)
- Background: `#111111`
- Border-right: `1px solid #222222`
- Logo: "VoiceScope" in Inter 16px weight 600
- Nav items: flat, no border-radius, 40px height
- Active: `border-left: 2px solid #818cf8` + `background: rgba(129,140,248,0.08)`
- Hover: `background: rgba(255,255,255,0.03)`

### Content Area
- Background: `#0a0a0a`
- Max-width: 1200px
- Padding: `32px 40px`
- Section spacing: `48px`

---

## Screen Layouts

### Screen 1: Overview

```
┌──────────────────────────────────────────────────────┐
│  Overview                                   [Refresh]│
│──────────────────────────────────────────────────────│
│                                                      │
│  ┌────────────────────┐ ┌──────────┐ ┌──────────┐   │
│  │ TRUTH SCORE        │ │ RUNS     │ │ ALERTS   │   │
│  │ 0.87               │ │ 1,247    │ │ 2 active │   │
│  │ +3% ↑              │ │ +12% ↑   │ │          │   │
│  │ [sparkline]        │ │          │ │          │   │
│  └────────────────────┘ └──────────┘ └──────────┘   │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  TRUTH SCORE TREND                             │  │
│  │  [area chart — last 7 days]                    │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────┐ ┌──────────────────────┐   │
│  │ ACTIVE ALERTS        │ │ RECENT RUNS          │   │
│  │ ● Hallu rate > 5%    │ │ abc-123  billing  87 │   │
│  │ ● Quality < 70       │ │ xyz-789  support  72 │   │
│  │                      │ │ jkl-456  cancel   91 │   │
│  └──────────────────────┘ └──────────────────────┘   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Screen 2: Runs

```
┌──────────────────────────────────────────────────────┐
│  Runs                                     [Analyze ↓]│
│──────────────────────────────────────────────────────│
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │ Search runs...                          [Filter]│  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │ RUN ID      INTENT     SCORE  STATUS  DATE    │  │
│  │────────────────────────────────────────────────│  │
│  │ abc-123     billing    87     ✅     2m ago   │  │
│  │ xyz-789     support    72     ⚠️     5m ago   │  │
│  │ jkl-456     cancel     91     ✅     12m ago  │  │
│  │ pqr-012     shipping   —      ❌     1h ago   │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  (Click a row → opens run detail slide-over)         │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Run Detail (Slide-over panel, not a new page)

```
┌──────────────────────────────┐
│  Run abc-123            [×]  │
│──────────────────────────────│
│                              │
│  billing dispute             │
│  (24px, weight 500)          │
│                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ │
│  │ ⚠️    │ │ ✅    │ │ ❌    │ │
│  │neg   │ │res   │ │none  │ │
│  │senti-│ │out-  │ │hallu-│ │
│  │ment  │ │come  │ │cin.  │ │
│  └──────┘ └──────┘ └──────┘ │
│                              │
│  ── Validation Harness ──    │
│                              │
│  0.87                        │
│  (48px, JetBrains Mono)      │
│  HIGH CONFIDENCE             │
│                              │
│  ── Layer Breakdown ──       │
│                              │
│  Schema      ████████░░ 0.95 │
│  Citations   ██████░░░░ 0.80 │
│  Facts       ███████░░░ 0.90 │
│  Sentiment   ███████░░░ 0.85 │
│  Outcome     █████░░░░░ 0.70 │
│  Escalation  ███████░░░ 0.90 │
│                              │
│  ── Transcript ──            │
│                              │
│  Agent: Hi, thank you...    │
│  Customer: Hi, I was...     │
│  Agent: I understand...     │
│                              │
└──────────────────────────────┘
```

### Screen 3: Settings

```
┌──────────────────────────────────────────────────────┐
│  Settings                                            │
│──────────────────────────────────────────────────────│
│                                                      │
│  [Providers] [Guardrails] [Alerts] [Schemas] [QA]   │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  LLM Provider                                  │  │
│  │                                                │  │
│  │  Provider    [OpenAI        ▾]                 │  │
│  │  Model       [gpt-4o        ▾]                 │  │
│  │  API Key     [sk-••••••••••••]                 │  │
│  │                                                │  │
│  │  [Save]                                        │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Interactions

| Element | Interaction |
|---------|------------|
| Nav items | Click → route change, border-left animation 150ms |
| Cards | Hover → subtle background shift to `#1a1a1a` |
| Table rows | Hover → background `#111111` |
| Run row | Click → slide-over panel from right, 200ms ease |
| Slide-over | Click overlay or × → close, 150ms ease |
| Buttons | Hover → color shift, 150ms ease |
| Inputs | Focus → border color `#818cf8`, 150ms ease |
| Theme toggle | Sun/Moon icon swap, 200ms rotate |

---

## Loading States

- **Skeleton loaders:** pulsing `#1a1a1a` → `#222222` animation
- **Spinner:** 20px, `border: 2px solid #222222` + `border-top: 2px solid #818cf8`
- **Inline:** text shimmer effect

---

## Empty States

- Center-aligned, muted text
- Icon (Lucide, 48px, `#666666`)
- Title: 16px, `#ededed`
- Description: 14px, `#666666`
- CTA button if actionable

---

## Responsive

| Breakpoint | Behavior |
|-----------|----------|
| >1200px | Full layout, sidebar + content |
| 768-1200px | Sidebar collapsed to icons (60px) |
| <768px | Sidebar hidden, hamburger menu |

---

## Icons

Lucide React, stroke-width 1.5, 16px default.

| Use | Icon |
|-----|------|
| Overview | `LayoutDashboard` |
| Runs | `List` |
| Settings | `Settings` |
| Upload | `Upload` |
| Alert | `AlertTriangle` |
| Success | `CheckCircle2` |
| Error | `XCircle` |
| Trend up | `TrendingUp` |
| Trend down | `TrendingDown` |
| Sun/Moon | `Sun` / `Moon` |
| Play | `Play` |
| Close | `X` |
| Search | `Search` |
| Filter | `Filter` |
| Refresh | `RefreshCw` |

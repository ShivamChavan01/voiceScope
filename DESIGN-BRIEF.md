# VoiceScope — Frontend Design Brief (v2)

## Design Inspiration: Claude.ai

Match Claude's aesthetic: **warm, clean, minimal, confident.** Not a cold developer dashboard. Not a data-heavy monitoring tool. A warm, approachable interface that happens to be powerful.

---

## Claude's Design DNA

| Element | Claude Does | VoiceScope Should |
|---------|-------------|-------------------|
| Background | Warm cream `#faf9f7` | Same warm cream |
| Sidebar | Slightly darker warm `#f0ede8` | Same warm tone |
| Text | Near-black `#1a1a1a` | Same |
| Accent | Warm terracotta/brown | Indigo `#6366f1` (our brand) |
| Borders | Almost invisible, warm gray | `#e8e5df` |
| Corners | Generous radius (12-16px) | Same |
| Typography | Clean, medium weight, generous size | Inter 400/500 |
| Spacing | Very generous whitespace | 24-32px padding |
| Shadows | None — color shift only | Same |
| Icons | Simple, thin strokes | Lucide, stroke-width 1.5 |
| Cards | Flat, border-only, no elevation | Same |
| Buttons | Rounded, minimal, warm | Rounded-lg, flat |
| Dark mode | Not default — warm light first | Light default, dark toggle |

---

## Color System

### Light Mode (Default)

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg` | `#faf9f7` | Page background (warm cream) |
| `--bg-sidebar` | `#f0ede8` | Sidebar background |
| `--bg-card` | `#ffffff` | Card/panel backgrounds |
| `--bg-hover` | `#f5f3ef` | Hover states |
| `--border` | `#e8e5df` | Subtle borders |
| `--text` | `#1a1a1a` | Primary text |
| `--text-secondary` | `#6b6560` | Labels, descriptions |
| `--text-muted` | `#9c9590` | Timestamps, meta |
| `--accent` | `#6366f1` | Indigo — buttons, active states |
| `--accent-light` | `#eef2ff` | Accent background tints |
| `--success` | `#16a34a` | Passed, resolved |
| `--warning` | `#d97706` | Warning, medium |
| `--error` | `#dc2626` | Failed, error |

### Dark Mode

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg` | `#1a1a1a` | Page background |
| `--bg-sidebar` | `#232323` | Sidebar |
| `--bg-card` | `#2a2a2a` | Cards |
| `--bg-hover` | `#333333` | Hover |
| `--border` | `#3a3a3a` | Borders |
| `--text` | `#f0ede8` | Primary (warm off-white) |
| `--text-secondary` | `#a09890` | Labels |
| `--text-muted` | `#706860` | Meta |

---

## Typography

- **Font**: Inter
- **Sizes**:
  - Page title: 24px, weight 600
  - Section title: 18px, weight 600
  - Card title: 14px, weight 500
  - Body: 14px, weight 400
  - Small/meta: 12px, weight 400
  - Metric value: 28px, weight 600, font-family `JetBrains Mono`
- **Line height**: 1.6 for body
- **Letter spacing**: normal (not tight, not wide)

---

## Global Layout

```
┌────────────┬────────────────────────────────────────────┐
│            │                                            │
│  Sidebar   │         Content Area                       │
│  260px     │         (max-width: 960px, centered)       │
│            │                                            │
│  ┌──────┐  │  ┌──────────────────────────────────────┐  │
│  │Voice │  │  │                                      │  │
│  │Scope │  │  │  Page content here                   │  │
│  │  🎙️  │  │  │                                      │  │
│  ├──────┤  │  │                                      │  │
│  │      │  │  │                                      │  │
│  │ Nav  │  │  │                                      │  │
│  │ Items│  │  │                                      │  │
│  │      │  │  │                                      │  │
│  │      │  │  └──────────────────────────────────────┘  │
│  │      │  │                                            │
│  │──────│  │                                            │
│  │ user │  │                                            │
│  └──────┘  │                                            │
└────────────┴────────────────────────────────────────────┘
```

### Sidebar

- Background: `--bg-sidebar` (warm)
- Width: 260px
- **Top**: Logo + "VoiceScope" wordmark (20px, weight 600)
- **Middle**: Navigation items — vertical list, generous padding
  - Each item: icon (20px) + label (14px, weight 500)
  - Spacing between items: 4px
  - Item padding: 10px 16px
  - Border-radius: 10px
  - Active: `--accent-light` background + `--accent` text + left border indicator
  - Hover: `--bg-hover` background
- **Bottom**: User section (theme toggle)
- **No top bar** — page title is part of content area (Claude style)

### Content Area

- Centered, max-width 960px
- Padding: 48px top, 32px sides
- Page title: 24px, weight 600, bottom margin 32px
- Sections separated by 48px vertical spacing

---

## Page 1: Dashboard Home

### KPI Cards (4 in a row)

```
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│  📞                  │ │  💰                  │ │  🔢                  │ │  ⚠️                   │
│  Total Calls         │ │  Average Cost        │ │  Total Tokens        │ │  Hallucination Rate  │
│                      │ │                      │ │                      │ │                      │
│  1,247               │ │  $0.034              │ │  2.4M                │ │  2.1%                │
│  +12% from last week │ │  -8% from last week  │ │  +15% from last week │ │  -0.3% from last week│
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘ └──────────────────────┘
```

Card style:
- Background: `--bg-card` (white)
- Border: 1px `--border`
- Border-radius: 14px
- Padding: 20px
- No shadow
- Icon: small colored circle (24px) with icon inside, tinted background
- Label: `--text-secondary`, 13px
- Value: `--text`, 28px, weight 600, JetBrains Mono
- Trend: 12px, green/red with arrow icon

### Charts Row

```
┌─────────────────────────────────────┐ ┌─────────────────────┐
│  Calls Over Time                    │ │  Outcome Split       │
│                                     │ │                      │
│                                     │ │      ┌──────┐        │
│  ···························         │ │     /  68%  \       │
│  ·                  ···             │ │    | Resolved|       │
│  ·           ···                    │ │     \  24%  /       │
│  ·     ···                          │ │      └──────┘        │
│  ·····                              │ │       Esc 8%         │
│  ─────────────────────              │ │                      │
│  Mon Tue Wed Thu Fri Sat Sun        │ │  ● Resolved          │
│                                     │ │  ● Unresolved        │
│                                     │ │  ● Escalated         │
└─────────────────────────────────────┘ └─────────────────────┘
```

Chart style:
- Background: `--bg-card`
- Border: 1px `--border`
- Border-radius: 14px
- Padding: 24px
- Title: 16px, weight 600, margin-bottom 16px
- Grid lines: `--border` color, very subtle
- Line chart: indigo line, 2px width, gradient fill below (indigo at 10% opacity)
- Donut chart: indigo for resolved, warm yellow for unresolved, warm red for escalated
- No axis lines — only grid lines

### Recent Calls

```
┌──────────────────────────────────────────────────────────────────────┐
│  Recent Calls                                           View all →  │
│                                                                      │
│  Run ID          Intent             Score    Outcome      Time       │
│  ─────────────────────────────────────────────────────────────────── │
│  abc-123-def     billing dispute     87     ✅ Resolved   2m ago    │
│  xyz-789-ghi     tech support        72     ⚠️ Escalated  5m ago    │
│  jkl-456-mno     cancellation        91     ✅ Resolved   12m ago   │
│  pqr-012-stu     shipping issue      —      ❌ Failed     1h ago    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

Table style:
- Background: `--bg-card`
- Border: 1px `--border`
- Border-radius: 14px
- No internal borders — rows separated by `--border` bottom
- Header: `--text-muted`, 12px, uppercase, weight 500
- Rows: `--text`, 14px
- Row hover: `--bg-hover`
- Run ID: JetBrains Mono, 13px
- Score: colored pill badge
- "View all →" link: `--accent`, 14px

---

## Page 2: Call Analysis

### Layout: Two columns (40/60 split)

```
┌───────────────────────┐ ┌─────────────────────────────────────────┐
│                       │ │                                         │
│  Analyze a Call       │ │  Analysis Result                        │
│                       │ │                                         │
│  ┌─────────────────┐  │ │  ┌────────┐ ┌────────┐ ┌────────┐     │
│  │                 │  │ │  │Intent  │ │Senti-  │ │Outcome │     │
│  │  📁 Drop audio  │  │ │  │        │ │ment    │ │        │     │
│  │  file here      │  │ │  │billing │ │⚠️ neg  │ │✅ res  │     │
│  │                 │  │ │  │issue   │ │        │ │        │     │
│  │  mp3, wav, m4a  │  │ │  └────────┘ └────────┘ └────────┘     │
│  │  Max 25MB       │  │ │                                         │
│  └─────────────────┘  │ │  ── Validation Harness ──               │
│                       │ │                                         │
│  ── or enter run ID ──│ │  Truth Score                            │
│  ┌─────────────────┐  │ │  0.87  HIGH CONFIDENCE                  │
│  │ run-abc-123     │  │ │  ████████████████████░░░░░░░  87%       │
│  └─────────────────┘  │ │                                         │
│                       │ │  Layer Breakdown                         │
│  [Analyze]            │ │  Schema       ████████████████░░  0.95  │
│                       │ │  Citations    ████████████░░░░░░  0.80  │
│                       │ │  Facts        ██████████████░░░░  0.90  │
│                       │ │  Sentiment    █████████████░░░░░  0.85  │
│                       │ │  Outcome      ██████████░░░░░░░░  0.70  │
│                       │ │  Escalation   ██████████████░░░░  0.90  │
│                       │ │                                         │
│                       │ │  ── Transcript ──                       │
│                       │ │  ┌─────────────────────────────────────┐│
│                       │ │  │ Agent: Hi, thank you for calling.  ││
│                       │ │  │ Customer: I need help with...      ││
│                       │ │  └─────────────────────────────────────┘│
│                       │ │                                         │
└───────────────────────┘ └─────────────────────────────────────────┘
```

Upload zone:
- Dashed border (2px, `--border`)
- Border-radius: 14px
- Centered icon + text
- On drag: border turns indigo, background tints

Analysis badges (4 cards):
- Background: `--bg-card`
- Border: 1px `--border`
- Border-radius: 12px
- Padding: 16px
- Small icon (colored), label (12px, `--text-muted`), value (16px, weight 600)

Harness score:
- Large number: 32px, weight 700, JetBrains Mono
- Confidence badge: pill, indigo background at 10%, indigo text
- Progress bar: 8px height, rounded, indigo fill on `--bg-hover` track

Layer breakdown:
- Each layer: label (14px, `--text-secondary`, width 100px) + bar + score
- Bar: 6px height, rounded, indigo fill on `--bg-hover` track
- Score: 13px, JetBrains Mono, `--text-secondary`

Transcript:
- Background: `--bg` (slightly recessed)
- Border-radius: 12px
- Padding: 20px
- Monospace or regular font, 14px
- Speaker labels in bold

---

## Page 3: Monitoring

### Time Range (top)

```
  Last hour    Last 24h    Last 7 days    Last 30 days
```

Pill buttons:
- Active: `--accent` background, white text
- Inactive: transparent, `--text-secondary`, border `--border`
- Border-radius: 8px, padding: 8px 16px

### KPI Row (5 cards)

Same card style as Dashboard but slightly smaller values (24px instead of 28px).

### Quality Trend (full width)

Same chart style as Dashboard. Area chart with indigo gradient.

### Alerts + Incidents (two columns)

```
┌─────────────────────────────┐ ┌──────────────────────────────┐
│  Alert Rules                │ │  Recent Incidents            │
│                             │ │                              │
│  ┌───────────────────────┐  │ │  🔴 Hallucination 7.2%      │
│  │ ⚠️ Hallu rate > 5%    │  │ │     2 minutes ago           │
│  │ Window: 60 min        │  │ │     Triggered by: Hallu > 5%│
│  │ ✅ Active              │  │ │                              │
│  └───────────────────────┘  │ │  🟡 Escalation rate 11.1%   │
│                             │ │     1 hour ago               │
│  ┌───────────────────────┐  │ │     Triggered by: Esc > 10% │
│  │ 📧 Quality < 70       │  │ │                              │
│  │ Window: 30 min        │ │  🔴 Quality score 62          │
│  │ ✅ Active              │ │     3 hours ago               │
│  └───────────────────────┘  │ │     Triggered by: Score < 70│
│                             │ │                              │
│  [Create new rule]          │ └──────────────────────────────┘
└─────────────────────────────┘
```

Alert rule card:
- Left colored indicator bar (4px, green if active)
- Rule name: 14px, weight 500
- Details: 12px, `--text-muted`
- Status badge: small pill

Incident item:
- Left colored dot (8px circle)
- Metric name + value: 14px, weight 500
- Time: 12px, `--text-muted`
- Rule reference: 12px, `--text-secondary`

---

## Page 4: Self-Improvement

### Two Columns: Weights + Benchmark

```
┌─────────────────────────────┐ ┌──────────────────────────────┐
│  Layer Weights              │ │  Benchmark Results            │
│                             │ │                               │
│  Schema       ████████░░    │ │  Tests run: 10                │
│  Citations    ██████░░░░    │ │  Avg truth score: 0.771       │
│  Facts        ███████░░░    │ │                               │
│  Sentiment    ██████░░░░    │ │  Per-layer accuracy:          │
│  Outcome      █████░░░░░    │ │  Sentiment:    90%  ████████░ │
│  Escalation   ██████░░░░    │ │  Outcome:      70%  ██████░░░ │
│  Cross-check  ██████░░░░    │ │  Hallucination: 85%  ███████░░ │
│  Duplicate    ████████░░    │ │  Escalation:   88%  ████████░ │
│                             │ │                               │
│  [Recalibrate]             │ │  Weakest: outcome_evidence    │
│                             │ │  Strongest: timestamp         │
│                             │ │                               │
│                             │ │  [Run Benchmark]              │
└─────────────────────────────┘ └──────────────────────────────┘
```

Weight bars: same horizontal bar style as harness layer breakdown.
Benchmark accuracy bars: same but with percentage labels.

### Prompt Suggestions (full width)

```
┌──────────────────────────────────────────────────────────────────┐
│  Improvement Suggestions                                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                                                              ││
│  │  ⚠️  outcome_evidence layer fails 30% of the time           ││
│  │                                                              ││
│  │  The analysis claims calls are "resolved" but no evidence   ││
│  │  markers (confirmation phrases, resolution statements) are  ││
│  │  found in the transcript.                                    ││
│  │                                                              ││
│  │  → Add explicit outcome evidence markers to the analysis    ││
│  │    prompt. Require transcript quotes for each claim.         ││
│  │                                                              ││
│  │  Confidence: 0.85 · 3 occurrences                           ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                                                              ││
│  │  ⚠️  Citations miss 20% of report findings                  ││
│  │                                                              ││
│  │  The report includes key findings that aren't backed by     ││
│  │  direct transcript quotes.                                   ││
│  │                                                              ││
│  │  → Require transcript citations for each key finding in     ││
│  │    the report generation prompt.                             ││
│  │                                                              ││
│  │  Confidence: 0.78 · 2 occurrences                           ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

Suggestion card:
- Background: `--bg-card`
- Border: 1px `--border`
- Border-radius: 14px
- Padding: 24px
- Warning icon + title: 16px, weight 600
- Description: 14px, `--text-secondary`, generous line-height
- Suggestion: 14px, `--text`, weight 500, prefixed with `→`
- Metadata: 12px, `--text-muted`

### Run Improvement Button

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  [▶  Run Full Improvement Cycle]                                │
│                                                                  │
│  Runs benchmark → optimizes weights → tracks patterns →          │
│  generates suggestions. Takes about 30 seconds.                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Button: large, indigo, rounded-lg, centered, with description below.

### Optimization History (full width chart)

Line chart showing truth score improving over optimization runs. Same chart style.

---

## Component Specs

### Button

```
Primary:   bg #6366f1, hover #4f46e5, text white, rounded-lg (10px), px-5 py-2.5, font-weight 500
Secondary: bg transparent, border 1px #e8e5df, text #6b6560, hover bg #f5f3ef
Ghost:     bg transparent, text #6b6560, hover bg #f5f3ef
Danger:    bg #dc2626, hover #b91c1c, text white
```

### Badge

```
Resolved:    bg #dcfce7, text #16a34a, border #bbf7d0
Unresolved:  bg #fef3c7, text #d97706, border #fde68a
Escalated:   bg #fee2e2, text #dc2626, border #fecaca
High:        bg #eef2ff, text #6366f1, border #c7d2fe
Medium:      bg #fef3c7, text #d97706, border #fde68a
Low:         bg #fee2e2, text #dc2626, border #fecaca
```

### Input

```
Background: white
Border: 1px #e8e5df
Border-radius: 10px
Padding: 10px 14px
Focus: border #6366f1, ring 3px #6366f1 at 10% opacity
Placeholder: #9c9590
```

### Card

```
Background: white
Border: 1px #e8e5df
Border-radius: 14px
Padding: 24px
No shadow
```

### Dialog/Modal

```
Backdrop: black at 40% opacity
Card: white, border-radius 16px, padding 32px
Max-width: 480px
Close button: top-right, ghost style
```

---

## Icons (Lucide, stroke-width 1.5)

| Use | Icon |
|-----|------|
| Dashboard | `LayoutDashboard` |
| Calls | `Phone` |
| Monitoring | `Activity` |
| Improve | `Brain` |
| QA | `ClipboardCheck` |
| Settings | `Settings` |
| Upload | `UploadCloud` |
| Alert | `AlertTriangle` |
| Check | `CheckCircle2` |
| Error | `XCircle` |
| Trend up | `TrendingUp` |
| Trend down | `TrendingDown` |
| Sun/Moon | `Sun` / `Moon` |
| Play | `Play` |
| Plus | `Plus` |
| Arrow right | `ArrowRight` |
| Chevron down | `ChevronDown` |

---

## Interactions

1. **Theme toggle**: Sun/Moon in sidebar bottom → instant switch, no flash
2. **Nav click**: Smooth page transition, active state updates
3. **Upload**: Drag over → border highlights indigo → drop → loading spinner → result slides in
4. **Time range**: Click pill → charts fade and reload
5. **Run improvement**: Click → button shows spinner → results animate in
6. **Create alert**: Click → centered modal with form
7. **Row hover**: Subtle background shift
8. **Mobile**: Sidebar collapses to hamburger, content goes full-width

---

## What NOT To Do

- ❌ No rainbow colors — one accent (indigo)
- ❌ No heavy shadows — color shift only
- ❌ No pure black backgrounds — warm tones
- ❌ No tiny text — minimum 12px
- ❌ No cramped spacing — generous whitespace
- ❌ No decorative elements — everything functional
- ❌ No gradients on text — flat colors
- ❌ No busy layouts — progressive disclosure

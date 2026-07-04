# OpenDesign Prompt — VoiceScope Dashboard (Dark Claude)

Copy everything below into OpenDesign:

---

Design a web dashboard called "VoiceScope" — an open-source voice AI observability platform. The design must be EXACTLY like Claude.ai's dark mode aesthetic. Super dark, premium, sophisticated. NOT a generic SaaS dashboard. NOT cartoonish. Think: Claude.ai dark mode meets Datadog's information density meets a luxury brand's website.

**ONLY 2 PAGES: Dashboard Home + Call Analysis.**

---

## Color System — SUPER DARK

### Primary Palette

| Token | Hex | Role |
|-------|-----|------|
| Canvas | #0d0d0d | Page background — near black |
| Surface Sidebar | #111111 | Sidebar — slightly lighter than canvas |
| Surface Card | #1a1a1a | Card surfaces — dark charcoal |
| Surface Elevated | #222222 | Elevated surfaces, dropdowns, modals |
| Surface Recessed | #141414 | Recessed areas, code blocks, transcript boxes |
| Surface Hover | #252525 | Hover states on cards and rows |
| Border | #2a2825 | Card borders, dividers — warm dark taupe |
| Border Subtle | #1f1e1c | Very subtle internal dividers |
| Border Active | #3a3835 | Active/focus borders |

### Text

| Token | Hex | Role |
|-------|-----|------|
| Text Primary | #f0ebe3 | Headlines, primary text — warm near-white |
| Text Body | #c4bfb6 | Body copy |
| Text Muted | #6b6760 | Captions, timestamps, metadata |
| Text Inverse | #0d0d0d | Text on light/indigo backgrounds |

### Accent — Indigo

| Token | Hex | Role |
|-------|-----|------|
| Accent | #818cf8 | Primary accent — buttons, active states, links (lighter indigo for dark bg) |
| Accent Hover | #a5b4fc | Accent hover state |
| Accent Soft | rgba(129,140,248,0.12) | Indigo at 12% — hover tints, active backgrounds |
| Accent Muted | rgba(129,140,248,0.06) | Indigo at 6% — very subtle tints |

### Status

| Token | Hex | Role |
|-------|-----|------|
| Success | #4ade80 | Passed, resolved, healthy |
| Success Soft | rgba(74,222,128,0.12) | Success background tint |
| Warning | #fbbf24 | Warning, medium confidence |
| Warning Soft | rgba(251,191,36,0.12) | Warning background tint |
| Error | #f87171 | Failed, critical, hallucination detected |
| Error Soft | rgba(248,113,113,0.12) | Error background tint |

---

## Typography

- **Hero numbers**: JetBrains Mono, 48-64px, weight 500, color #f0ebe3
- **Page title**: Georgia/Times serif, 28px, weight 400, italic, letter-spacing -0.5px, color #f0ebe3
- **Section headers**: Georgia/Times serif, 16px, weight 400, italic, color #6b6760, with em-dash装饰: "— Analysis —"
- **Card title**: Inter sans, 13px, weight 500, color #6b6760, uppercase, letter-spacing 0.8px
- **Body**: Inter sans, 14px, weight 400, color #c4bfb6
- **Caption**: Inter sans, 12px, weight 400, color #6b6760
- **Overline**: Inter sans, 11px, weight 500, uppercase, letter-spacing 0.8px, color #6b6760
- **Code/metrics**: JetBrains Mono, 14px, weight 400, color #f0ebe3
- **Line height**: 1.6 body, 1.3 headings

---

## Pages — ONLY 2

1. **Dashboard Home** — Hero metrics, charts, recent calls
2. **Call Analysis** — Upload, results, transcript, layer breakdown

---

## Layout — EXACT Claude.ai Dark Mode Structure

```
┌──────────────────────┬──────────────────────────────────────────────────┐
│  🔵 VoiceScope       │                                                  │
│──────────────────────│  Dashboard                     (serif italic)   │
│                      │  Overview of your voice AI pipeline             │
│  ▌ Dashboard         │                                                  │
│    Calls             │  ══════════════════════════════════════════════  │
│    Analysis          │                                                  │
│    Monitoring        │  ┌──────────────────────────┐ ┌──────────┐      │
│    Self-Improve      │  │  HERO CARD (2x wide)     │ │ Small    │      │
│    QA                │  │  1,247                    │ │ Card     │      │
│                      │  │  (64px mono)              │ │ 2.1%     │      │
│──────────────────────│  │  + chart                  │ │          │      │
│                      │  └──────────────────────────┘ └──────────┘      │
│  Settings            │                                                  │
│  ☾ Dark              │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│                      │  │ Card     │ │ Card     │ │ Card     │        │
│                      │  └──────────┘ └──────────┘ └──────────┘        │
│                      │                                                  │
│                      │  ══════════════════════════════════════════════  │
│                      │                                                  │
│                      │  Full-width section...                          │
└──────────────────────┴──────────────────────────────────────────────────┘
```

### Sidebar — EXACTLY like Claude.ai Dark Mode

**Structure:**
```
┌──────────────────────────┐
│  🔵  VoiceScope          │  ← Logo bar
│──────────────────────────│
│                          │
│  ◻  Dashboard            │  ← Flat nav items, NO rounded buttons
│  ◻  Calls                │     NO border-radius on items
│  ◻  Analysis             │     Clean, minimal, flat
│  ◻  Monitoring           │
│  ◻  Self-Improve         │
│  ◻  QA                   │
│                          │
│──────────────────────────│
│                          │
│  ◻  Settings             │  ← Bottom section
│  ☾  Dark                 │  ← Theme toggle
└──────────────────────────┘
```

**Dimensions & Colors:**
- Background: #111111 (warm dark — NOT black, NOT gray)
- Width: 260px
- Border-right: 1px solid #2a2825
- Height: 100vh, fixed, no scroll

**Logo Bar:**
- Height: 56px
- Display: flex, align-items: center, gap 12px
- Padding: 0 24px
- Border-bottom: 1px solid #2a2825
- Icon: Lucide `Mic`, 18px, color #818cf8
- Text: "VoiceScope", Georgia serif italic, 16px, weight 400, color #f0ebe3
- Letter-spacing: -0.3px

**Nav Items — FLAT, NO ROUNDED BUTTONS:**
- Display: flex, align-items: center, gap 12px
- Height: 40px
- Padding: 0 24px (full width, NO margin, NO border-radius)
- Font: Inter, 14px, weight 400
- Color default: #6b6760
- Color hover: #c4bfb6
- Color active: #f0ebe3
- Background default: transparent
- Background hover: rgba(255,255,255,0.03)
- Background active: rgba(129,140,248,0.08)
- Border-left: 2px solid transparent (default) → 2px solid #818cf8 (active)
- Padding-left: 22px (to compensate for border)
- Icon: Lucide, 16px, color inherits from text
- Transition: all 150ms ease
- NO border-radius anywhere — completely flat
- NO box-shadow anywhere
- NO outline on focus — just border-left color change

**Section Dividers in Sidebar:**
- Height: 1px
- Background: #2a2825
- Margin: 12px 24px
- Used between: main nav and bottom section

**Bottom Section:**
- Position: absolute, bottom 0, left 0, right 0
- Border-top: 1px solid #2a2825
- Padding: 12px 0
- Same flat nav item style as above
- Theme toggle: Sun/Moon icon, same style as nav items

### Content Area

- Background: #0d0d0d (same as canvas — seamless)
- Max-width: 1200px
- Padding: 40px 48px
- **Page title**: Serif italic, 28px, #f0ebe3
- **Section dividers**: Thin line (1px #2a2825) + centered serif italic text: "— Section Name —"
- **Section spacing**: 64px between major sections

---

## Page 1: Dashboard Home

### Hero Row (Asymmetric: 2 cards)

```
┌───────────────────────────────────────────────┐ ┌──────────────┐
│  TOTAL CALLS THIS WEEK                        │ │ Hallucination│
│  (11px, uppercase, #6b6760, letter-spacing)   │ │ Rate         │
│                                               │ │              │
│     1,247                                     │ │   2.1%       │
│     (JetBrains Mono, 64px, #f0ebe3)           │ │  (mono 36px) │
│                                               │ │  -0.3% ↓     │
│  +12% from last week (green, 13px)            │ │              │
│                                               │ └──────────────┘
│  ┌─────────────────────────────────────────┐  │
│  │  📈 Calls over time — area chart        │  │
│  │  indigo gradient fill on dark bg        │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

Hero card:
- Background: #1a1a1a (dark card)
- Border: 1px solid #2a2825
- Border-radius: 16px
- Padding: 28px
- **Title**: 11px sans weight 500 #6b6760 uppercase letter-spacing 0.8px
- **Number**: 64px JetBrains Mono #f0ebe3 (the premium metric effect)
- **Trend**: 13px sans #4ade80 (green) or #f87171 (red)
- **Chart**: embedded at bottom, dark background, indigo gradient fill

Small card:
- Same styling but number is 36px mono

### Secondary Row (3 uniform cards)

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Average Cost │ │ Total Tokens │ │ Avg Duration │
│              │ │              │ │              │
│   $0.034     │ │   2.4M       │ │   2m 34s     │
│   (mono 28px)│ │   (mono 28px)│ │   (mono 28px)│
│  -8% ↓       │ │  +15% ↑      │ │  +3% ↑       │
└──────────────┘ └──────────────┘ └──────────────┘
```

Cards:
- Background: #1a1a1a
- Border: 1px solid #2a2825
- Border-radius: 12px
- Padding: 24px

### Section Divider

```
─────────── Outcome Distribution ───────────
```

Serif italic, centered, #6b6760, with thin lines (#2a2825) extending to edges.

### Outcome + Recent Calls

```
┌─────────────────────────────┐ ┌─────────────────────────────────┐
│  Outcome Split              │ │  Recent Calls            → all │
│                             │ │                                 │
│  ┌──────────────────────┐   │ │  Run ID       Intent    Score  │
│  │                      │   │ │  ──────────────────────────────│
│  │    ┌──────────┐      │   │ │  abc-123     billing    87 ✅  │
│  │   /  Resolved \     │   │ │  xyz-789     support    72 ⚠️  │
│  │  |    68%      |    │   │ │  jkl-456     cancel     91 ✅  │
│  │   \  24%      /     │   │ │  pqr-012     shipping   — ❌   │
│  │    └──────────┘      │   │ │                                 │
│  │     Escalated 8%     │   │ │                                 │
│  └──────────────────────┘   │ │                                 │
│                             │ │                                 │
│  ● Resolved  68%            │ │                                 │
│  ● Unresolved 24%           │ │                                 │
│  ● Escalated 8%             │ │                                 │
└─────────────────────────────┘ └─────────────────────────────────┘
```

---

## Page 2: Call Analysis

### Hero: Upload + Result Side by Side

```
┌──────────────────────────┐ ┌──────────────────────────────────┐
│                          │ │                                  │
│  Analyze a Call          │ │  billing dispute                 │
│  (serif italic, 24px)    │ │  (serif italic, 48px)            │
│                          │ │                                  │
│  ┌────────────────────┐  │ │  ┌──────┐ ┌──────┐ ┌──────┐    │
│  │  📁 Drop audio     │  │ │  │ ⚠️    │ │ ✅    │ │ ❌    │    │
│  │  file here         │  │ │  │neg   │ │res   │ │none  │    │
│  │                    │  │ │  │senti-│ │out-  │ │hallu-│    │
│  │  or enter run ID   │  │ │  │ment  │ │come  │ │cin.  │    │
│  │  ┌──────────────┐  │  │ │  └──────┘ └──────┘ └──────┘    │
│  │  │ run-abc-123  │  │  │ │                                  │
│  │  └──────────────┘  │  │ │  ── Validation Harness ──       │
│  │                    │  │ │                                  │
│  │  [Analyze]         │  │ │  0.87                            │
│  └────────────────────┘  │ │  (JetBrains Mono, 56px, #f0ebe3)│
│                          │ │                                  │
│                          │ │  HIGH CONFIDENCE                 │
│                          │ │  (sans, 12px, indigo, uppercase) │
│                          │ │                                  │
│                          │ │  ┌───────────────────────────┐   │
│                          │ │  │████████████████████░░░░░░░│   │
│                          │ │  └───────────────────────────┘   │
│                          │ │                                  │
└──────────────────────────┘ └──────────────────────────────────┘
```

### Layer Breakdown (with color strips)

```
────────── Layer Breakdown ──────────

┌──────────────────────────────────────────────────────────────┐
│ ██████████████████████████████████████████████ (green strip) │
│ Schema        ████████████████████░░░░░░░  0.95              │
├──────────────────────────────────────────────────────────────┤
│ ██████████████████████████████████████ (yellow strip)        │
│ Citations     ██████████████░░░░░░░░░░░░░  0.80              │
├──────────────────────────────────────────────────────────────┤
│ ██████████████████████████████████████████████ (green strip) │
│ Facts         █████████████████░░░░░░░░░░  0.90              │
├──────────────────────────────────────────────────────────────┤
│ ██████████████████████████████████████ (yellow strip)        │
│ Sentiment     ████████████████░░░░░░░░░░░  0.85              │
├──────────────────────────────────────────────────────────────┤
│ ████████████████████████ (red strip)                         │
│ Outcome       ██████████░░░░░░░░░░░░░░░░░  0.70              │
├──────────────────────────────────────────────────────────────┤
│ ██████████████████████████████████████████████ (green strip) │
│ Escalation    █████████████████░░░░░░░░░░  0.90              │
└──────────────────────────────────────────────────────────────┘
```

Each layer row:
- Left: 4px color strip (green >0.85, yellow 0.7-0.85, red <0.7)
- Background: #1a1a1a
- Border-bottom: 1px solid #1f1e1c (subtle)
- Label: 14px sans #c4bfb6
- Bar: 6px height, #818cf8 fill on #252525 track
- Score: 14px JetBrains Mono #6b6760

### Transcript

```
────────── Transcript ──────────

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Agent: Hi, thank you for calling Acme Corp. How can I      │
│  help you today?                                             │
│                                                              │
│  Customer: Hi, I was charged twice for my last subscription │
│  payment. Can you help?                                      │
│                                                              │
│  Agent: I understand your concern. Let me look into that    │
│  for you right away.                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Transcript box:
- Background: #141414 (recessed)
- Border: 1px solid #2a2825
- Border-radius: 12px
- Padding: 24px
- Text: 14px sans #c4bfb6, line-height 1.7
- Speaker labels: weight 600, #f0ebe3

---

## Component Specs

### Buttons

Primary: bg #818cf8, text #0d0d0d, rounded 10px, padding 12px 28px, weight 500, no shadow
Secondary: bg transparent, border 1px #2a2825, text #c4bfb6, rounded 10px, padding 12px 28px
Ghost: bg transparent, text #818cf8, no border, padding 8px 16px

### Data Callout Pill

Background: rgba(129,140,248,0.08) (subtle indigo tint)
Border: 1px solid rgba(129,140,248,0.15)
Border-radius: 8px
Padding: 8px 16px
Text: JetBrains Mono, 20px, #f0ebe3
Use for: key metrics that need emphasis

### Status Strip (on top of cards)

Height: 4px
Full width of card, top edge, border-radius 12px 12px 0 0
Green (#4ade80) = healthy/passed
Yellow (#fbbf24) = warning
Red (#f87171) = error/critical

### Badge

Background: based on status (green/yellow/red at 12% opacity)
Text: matching color
Border-radius: 6px
Padding: 3px 10px
Font: 12px sans weight 500

### Progress Bar

Height: 10px (hero) or 6px (inline)
Border-radius: 5px (hero) or 3px (inline)
Fill: #818cf8
Track: #252525

---

## Icons

Lucide React, stroke-width 1.5

| Use | Icon |
|-----|------|
| Dashboard | LayoutDashboard |
| Calls | Phone |
| Monitoring | Activity |
| Improve | Brain |
| QA | ClipboardCheck |
| Settings | Settings |
| Upload | UploadCloud |
| Alert | AlertTriangle |
| Success | CheckCircle2 |
| Error | XCircle |
| Trend up | TrendingUp |
| Trend down | TrendingDown |
| Sun/Moon | Sun / Moon |
| Play | Play |
| Arrow | ArrowRight |

---

## Anti-Patterns (DO NOT)

- ❌ Light/cream backgrounds — EVERYTHING is dark
- ❌ Cartoonish colors — only warm neutrals + indigo accent
- ❌ Shadows for depth — use background color shifts (#0d0d0d → #1a1a1a → #222222)
- ❌ Cold grays — every neutral has warm yellow-brown undertone
- ❌ Sans-serif headlines — use serif italic for editorial feel
- ❌ Crowded layouts — 64px section spacing, breathe
- ❌ Generic dashboard feel — make it feel like Claude.ai dark mode
- ❌ Multiple accent colors — one accent (indigo #818cf8) only
- ❌ White text on dark without warm tint — always use #f0ebe3 (warm), never #ffffff (cold)
- ❌ Rounded buttons in sidebar — FLAT nav items, NO border-radius, NO rounded pills
- ❌ Box shadows on sidebar items — completely flat, no depth effects
- ❌ Colored backgrounds on nav items — transparent by default, subtle tint on active only
- ❌ Bold/heavy nav text — weight 400 only, clean and light
- ❌ Icons larger than 16px in nav — small, subtle, secondary to text

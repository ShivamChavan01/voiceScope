# OpenDesign Prompt — VoiceScope Embedded Dashboard

Paste this into OpenDesign to generate visual mockups.

---

## Project

VoiceScope is a voice AI observability tool. It sits behind another AI — not a standalone product. The frontend shows what happened, shows if something's wrong, lets a human configure settings. 3 screens only.

## Design Direction

**Dark minimal AI company UI.** Think: Claude.ai dark mode meets Linear meets Raycast. Clean type, warm dark palette, no visual noise. Not a SaaS dashboard. Not cartoonish. A quiet, premium tool.

## Color System

| Token | Hex | Usage |
|-------|-----|-------|
| Canvas | #0a0a0a | Page background |
| Surface | #111111 | Cards, sidebar |
| Surface Elevated | #1a1a1a | Dropdowns, hover |
| Surface Recessed | #0f0f0f | Code, transcripts |
| Border | #222222 | Card borders |
| Text Primary | #ededed | Headlines |
| Text Secondary | #a1a1a1 | Body |
| Text Muted | #666666 | Captions |
| Accent | #818cf8 | Buttons, active |
| Success | #4ade80 | Passed |
| Warning | #fbbf24 | Warning |
| Error | #f87171 | Failed |

## Typography

- Headlines: Inter, 600 weight
- Body: Inter, 400 weight
- Metrics: JetBrains Mono, 500 weight
- Code/transcript: JetBrains Mono, 400 weight

## Layout

- Sidebar: 260px fixed, dark (#111111), flat nav items (no rounded buttons)
- Content: dark canvas (#0a0a0a), max-width 1200px
- Cards: #111111 background, #222222 border, 8px radius

## Screens to Generate

### Screen 1: Overview
- Hero row: 3 metric cards (truth score with sparkline, total runs, active alerts)
- Truth score trend chart (area chart, last 7 days)
- Bottom row: active alerts list + recent runs table

### Screen 2: Runs
- Search bar + filter button
- Table: run ID, intent, score, status badge, date
- Click row → slide-over panel from right with:
  - Intent headline
  - Sentiment/outcome/hallucination badges
  - Truth score (48px mono)
  - Layer breakdown (6 progress bars)
  - Transcript box (recessed background)

### Screen 3: Settings
- Tab bar: Providers | Guardrails | Alerts | Schemas | QA
- Providers tab: provider dropdown, model dropdown, API key input, save button
- Other tabs: similar form layouts

## Component Specs

### Card
- Background: #111111
- Border: 1px solid #222222
- Border-radius: 8px
- Padding: 20px

### Button (Primary)
- Background: #818cf8
- Text: #0a0a0a
- Border-radius: 8px
- Padding: 8px 16px

### Badge
- Background: status color at 12% opacity
- Text: status color
- Border-radius: 6px

### Table
- Header: #111111 bg, #666666 text, uppercase, 12px
- Row hover: #111111
- Border-bottom: 1px solid #222222

### Progress Bar
- Height: 6px, border-radius: 3px
- Fill: #818cf8, track: #1a1a1a

### Sidebar
- Flat nav items, no border-radius
- Active: border-left 2px solid #818cf8 + subtle indigo tint
- Hover: barely visible white tint

## Anti-Patterns (DO NOT)

- No light mode
- No rounded buttons in sidebar
- No shadows
- No cartoonish colors
- No cold grays (warm undertone only)
- No visual noise
- No more than 3 screens

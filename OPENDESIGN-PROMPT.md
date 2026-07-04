# OpenDesign Prompt — VoiceScope Dashboard (Dark Claude)

Use the design tokens, color system, typography, and layout specs from `DESIGN-PROMPT.md` in this repository to generate visual mockups for a voice AI observability dashboard.

---

## Project Context

**VoiceScope** is an open-source voice AI observability platform. It helps developers and QA teams analyze voice AI calls (customer service bots, support bots, telephony AI) by detecting hallucinations, verifying facts, tracking sentiment, and providing self-improvement loops.

### Only 2 Pages

1. **Dashboard Home** — Hero metrics (total calls, hallucination rate, cost, tokens), outcome distribution, recent calls table
2. **Call Analysis** — Upload audio or enter run ID, see analysis results: transcript, layer breakdown scores, sentiment, hallucination detection

### Design DNA (from DESIGN-PROMPT.md)

- **Palette**: Super dark canvas (#0d0d0d), dark sidebar (#111111), dark cards (#1a1a1a), warm near-white text (#f0ebe3), warm borders (#2a2825), indigo accent (#818cf8)
- **Typography**: Serif italic headlines (Georgia), sans body (Inter), monospace metrics (JetBrains Mono)
- **Feel**: Premium editorial magazine about data — NOT generic SaaS dashboard
- **Signature moves**: Oversized metric numbers (48-64px), asymmetric card grid, status color strips, serif section dividers with em-dashes
- **Sidebar**: FLAT nav items — NO rounded buttons, NO border-radius, NO box shadows

### Pages in Figma

Generate frames for each page with:
- Sidebar navigation (dark, 260px, flat nav items)
- Content area (dark canvas)
- Dark mode only

---

## What to Generate

1. **Dashboard Home** — Full page mockup with hero row (asymmetric 2+1 cards), secondary metrics row, outcome distribution, recent calls table
2. **Call Analysis** — Split view: upload form left, analysis results right. Transcript box, layer breakdown with color strips, sentiment badges

Use the exact hex values, spacing, border-radius, and typography from `DESIGN-PROMPT.md`. Do not invent new tokens. Do NOT add rounded corners to sidebar nav items.

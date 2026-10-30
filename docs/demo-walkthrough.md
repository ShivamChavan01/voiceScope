# Demo walkthrough

## 60–90 seconds

**0–15 seconds — Calls:** “VoiceScope reviews completed voice AI calls. Real calls and synthetic scenarios are labeled separately. Missing evidence remains visible instead of becoming a perfect score.”

**15–35 seconds — Forbidden promise:** Open the synthetic same-day refund promise. “This fictional company prohibits same-day refund guarantees. Here is the exact agent quote and the policy version applied.” Select the evidence turn to show its transcript context. “This detects an explicit promise; it does not claim a refund actually happened.”

**35–50 seconds — Escalation:** Open the synthetic escalation refusal. “The finding includes the caller's supervisor request and the agent's explicit refusal. A missing transfer log alone would not establish this violation.”

**50–60 seconds — No matches:** Open the compliant synthetic conversation. “No matches means neither of these two supported checks matched. It does not certify the whole call.”

**60–75 seconds — Real call:** Open the real Bolna STT-only call, then STT quality. “This is the original Bolna recording and a separate Deepgram pass with real timestamps. This call has no Bolna turn timestamps or confirmed reference speaker roles, so an aligned quality rate remains unavailable.”

**75–90 seconds — Engineering proof:** Open the uploaded call with evaluator warnings, then Evaluation checks. “The generated summary is labeled as AI-generated. These checks flag unsupported statements in the analysis for review; they are not confirmed violations by the call agent.”

## Rehearsal

Use **Explore sample calls** on Calls; seeding is repeatable and does not configure real company policies. Keep the actual call in a private local environment. Do not record credentials, phone numbers, or sensitive transcript content. Rehearse quote navigation after reloading the page. The current implementation is post-call inspection, not live speech repair.

## Current local verification — October 30

The private preview already contains the three labeled sample calls. The sample
loader does not install their fictional policies globally. The real uploaded call
has no configured company policies, but its saved summary and three evaluator
warnings are now visible in Findings. Those are separate from policy findings.
Browser checks verified both synthetic violation evidence links and the real saved
summary without another provider submission. Five tabs remain directly accessible.

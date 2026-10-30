# Speaker attribution

VoiceScope distinguishes speaker IDs from conversational roles. A diarization ID such as speaker 0 identifies a voice cluster within one recording. It does not identify a person or establish who is the agent.

## Role sources

| Source | Display | Behavior |
| --- | --- | --- |
| Explicit transcript label | Agent or Customer | Preserve `assistant`/`agent` and `user`/`customer` labels without calling a role model |
| Diarized audio and model inference | Agent · inferred or Customer · inferred | Infer roles from conversational context, independently of speaking order |
| Missing or inconclusive attribution | Speaker N · role unknown | Require review; never assign agent merely because a voice speaks first |
| Historical role without provenance | Agent · unverified or Customer · unverified | Display the legacy role with its uncertainty |

This is role attribution, not biometric identification. A caller name must come from supplied identity data or explicit evidence, not a guessed voice identity.

## Runtime flow

Bolna webhook ingestion prefers its supplied transcript. It preserves line-delimited role labels and skips a second transcription that would discard that evidence. Recording download remains the fallback when the supplied transcript is empty. The parsed source call and agent metadata are retained in the evaluation.

Regular audio upload and streaming upload both call `VoiceScopePipeline.attribute_speakers` before analysis. Deepgram explicitly requests paragraphs; word-level speaker IDs provide a fallback when paragraphs are absent. Missing diarization remains unknown. Whisper and Gemini text without speaker structure is not treated as proof that the entire conversation belongs to one person.

`raw_transcript` retains the original text. `transcript_speakers` holds turns and role provenance. `attributed_transcript` supplies roles to analysis and marks inferred roles visibly. Long-transcript chunking recognizes those annotated prefixes.

## Root causes and correction

The streaming path previously skipped speaker classification. The speaker classifier also defaulted the first voice to agent on failure. Bolna ingestion re-transcribed audio rather than preserving its supplied role labels.

The old failure behavior was reproduced directly against the repository's previous classifier with a simulated provider failure:

```text
before ['agent', 'customer']
after ['unknown', 'unknown']
```

Pstack design review found and corrected three additional cases: inferred labels breaking long-call chunking, an unknown speaker label merging into the previous agent's turn, and plain transcripts proceeding without attribution uncertainty.

## Executed verification

A real Chromium browser opened the replayed 72-second Bolna call. Its 20 transcript turns displayed 10 Agent labels and 10 Customer labels. The labels survived a page reload. No browser page errors occurred.

The actual recording was then uploaded through the Runs UI. The live Deepgram/Groq streaming path returned 12 diarized turns labeled Agent or Customer with inferred provenance. Those labels also survived a page reload with no browser page errors.

Private local screenshots and repeatable browser checks are stored under `/tmp/voicescope-live-qa/`:

```bash
node /tmp/voicescope-live-qa/check-speaker-ui.mjs
node /tmp/voicescope-live-qa/check-speaker-upload.mjs
```

The upload check invokes real provider services. These scripts use temporary local servers and private call data; they are session evidence rather than committed fixtures.

Deterministic regressions cover explicit caller-first roles, single speakers, failed and invalid model responses, missing diarization, word-level fallback, unknown labels, long-call chunking, shared streaming attribution, and persistence/reload. Run them with:

```bash
.venv/bin/pytest tests/test_speakers.py tests/test_speaker_integration.py tests/test_agents.py tests/test_stt_providers.py -q
npm --prefix frontend test
```

The full Python suite passed 403 tests. The frontend helper suite passed six tests. Changes remain local; no production deployment or historical production reprocessing occurred.

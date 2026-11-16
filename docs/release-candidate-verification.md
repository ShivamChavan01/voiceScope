# Private-instance release candidate

Local verification, November 17, 2026. This candidate combines the reviewed
storage/retrieval replacement, detector regressions and frontend dependency fixes.
It is not a production-readiness or real-call accuracy claim.

## Local verification

- Backend: 1,076 tests passed, including configured-database outages, receipt
  preflight, call-context deletion, explicit migration and SQLite snapshot/restore.
- Frontend: 77 tests passed, including the actual private setup template,
  authentication failures, evidence states and proxy boundaries.
- Python and frontend lint/type checks and the frontend production build passed.
- The frontend npm audit reported zero known advisories after removing the unused
  shadcn CLI dependency and updating affected lint dependencies within their ranges.
- The original 28-case policy set, 40 adversarial cases and 30 challenge cases
  passed their unchanged exact-match gates. These authored inputs now inform the
  implementation and are regression sets, not held-out production measurements.
- Misspelled promise words, fragmented statements and contextual answers require
  intent review. Language coverage remains explicitly bounded; see
  [evidence contracts](reliability.md).

Historical operational reports, real-call identifiers, recordings, credentials,
database copies and private test artifacts are not part of this release evidence.
Fresh browser journeys and a new container build were not executed in this local
pass. The exact pushed commit needs its own complete CI and container checks.

## Gates before customer deployment

1. Require CI success for the exact candidate commit, including the fresh Docker
   build, complete image dependency audit and private-file exclusion checks.
2. Configure server-only operator authentication and a matching backend key on
   the intended private frontend. Verify anonymous denial and authorized access.
3. Choose durable private storage for every local store, not only the primary
   PostgreSQL database. Rehearse [backup/restore](storage-reliability.md) and
   [semantic migration](semantic-retrieval.md) against isolated installation data.
4. Verify restart persistence and an authentication-preserving code rollback.
5. Verify a fresh authorized Bolna-originated webhook, recording provenance,
   duplicate/retry behavior and report reload on that exact deployment.

Free synthetic staging does not establish customer-data durability. Provider
calls, infrastructure changes and production promotion require their applicable
authorization. Production is not changed by these local checks.

# Private-instance storage and recovery

## Select storage deliberately

Without `DATABASE_URL`, runs, costs and metrics use their local SQLite stores.
With `DATABASE_URL`, they use PostgreSQL with TLS required. Connection failure
raises a sanitized error rather than selecting SQLite. The initial pool attempt
has a 15-second total timeout; waiting for another request's initialization lock
is separate. A later request can retry connection establishment.

Failed PostgreSQL connection or schema initialization blocks startup. Runtime
connection failures return HTTP 503 with `Cache-Control: no-store` and
`Retry-After: 5`. Authentication is still required. Query/schema programming
errors are not automatically reclassified as temporary connection failures.
The lightweight `/api/v1/health` endpoint remains a liveness check, not proof that
all storage is healthy. Verify an authenticated run read as part of readiness.

`DATABASE_URL` does not move policy rules, reference knowledge, webhook receipts,
STT artifacts or semantic retrieval to PostgreSQL. Configure a private persistent `DATA_DIR`
and review explicit path overrides before starting. Free staging without a disk
remains ephemeral. Do not point a customer instance at the public demo's storage.

## Snapshot and restore a SQLite database

Run from the repository root in a private operator environment:

```bash
.venv/bin/python -m tools.sqlite_snapshot /private/data/monitoring.db /private/backups/runs.sqlite
.venv/bin/python -m tools.sqlite_snapshot /private/backups/runs.sqlite /private/recovery/monitoring.db
```

These are example paths, not production commands to run automatically. The tool
opens the source read-only and uses SQLite's online backup API, including
committed WAL content. It checks the copied database and publishes a new file
without overwriting an existing destination. New snapshot files have mode 0600;
new destination directories have mode 0700. Existing parent-directory permissions
are not changed. The operation times out if its progress exceeds 30 seconds.
Keep snapshots outside Git, images, public assets and publicly shared directories.
They are not encrypted by this tool and may include transcripts or recordings.

To restore, copy into a new recovery directory, verify the data there, then stop
the application before switching its data paths. The tool does not overwrite or
switch a live deployment. Retain the old directory for recovery until the restored
instance has been checked.

Each snapshot is consistent for one SQLite database. It is not a coordinated
snapshot across stores. Pause ingestion and writes before taking a set that must
preserve report/receipt consistency. Inventory these separately:

- `monitoring.db` or `MONITORING_DB_PATH`: runs and reports in SQLite mode.
- `costs.db` or `COST_DB_PATH`: costs in SQLite mode.
- `policies.db` or `POLICY_DB_PATH`: active policy rules.
- `webhook_receipts/receipts.sqlite` under `DATA_DIR`: completed-event deduplication.
- Knowledge, QA, extraction and optimizer databases and their explicit overrides.
- `STT_REVIEW_DIR` or `DATA_DIR/stt_reviews`: expiring private STT artifacts.
- `SEMANTIC_DB_PATH` or `DATA_DIR/semantic/index.sqlite`: active knowledge and
  past-call semantic retrieval. See [semantic migration](semantic-retrieval.md).

For archived legacy installations, do not back up only Chroma's SQLite file:
its index files also matter. Use a
separately verified offline copy of the complete index directory, or a tested
rebuild from preserved source knowledge. Neither procedure is automated here.
For PostgreSQL, use its native backup/restore tools; this SQLite tool cannot
snapshot Neon/PostgreSQL. Restoring runs alone does not restore local receipts,
policies or STT evidence. Restored STT artifacts retain their original expiry.

## Evidence and limits

Regression tests exercise committed WAL state, uncommitted writes, invalid files,
private file permissions, timeout cleanup and overwrite rejection. Synthetic run
and webhook receipt snapshots are restored and read through fresh store instances.
See [candidate verification](release-candidate-verification.md) for the local
verification scope. Hosted backups, storage volumes and rollback remain unverified.

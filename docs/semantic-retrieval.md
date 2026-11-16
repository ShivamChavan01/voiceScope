# Local semantic retrieval

VoiceScope uses a private SQLite index and FastEmbed 0.9.1 with the fixed
`sentence-transformers/all-MiniLM-L6-v2` ONNX model. Both company knowledge and
past-call retrieval remain semantic searches using cosine similarity. No text,
recordings or API credentials are submitted to an embedding service.

The runtime requirements no longer install Chroma. Its expired exception has
been removed from the dependency-audit policy. The legacy SDK is used only for
explicit offline export in an isolated old environment, never by the application.

## Setup

`SEMANTIC_DB_PATH` defaults to `DATA_DIR/semantic/index.sqlite`. The `policy_kb`
and `voice_calls` namespaces have separate document IDs inside that database.
New files have mode 0600 and new directories mode 0700. Include this database in
private backups; it contains indexed policy and call text, metadata and vectors.

The first embedding operation can download public model assets. It does not send
input text during that download. Prepare the model before a customer demo:

```bash
export EMBEDDING_CACHE_DIR=/private/data/embedding_models
.venv/bin/python -c 'from storage.semantic_index import embedding_model; embedding_model()'
```

After assets are cached, set `EMBEDDING_LOCAL_ONLY=true` for offline operation.
Alternatively, set `SEMANTIC_MODEL_PATH` to a trusted local directory containing
the compatible ONNX model and tokenizer assets. Never use untrusted model files.
The model name is fixed in application code and cannot be selected by a policy,
webhook, transcript, imported document or API request.

`KnowledgeBase.reload()` computes replacement embeddings before a transaction
replaces the namespace. Failed embedding generation preserves the previous stored
index and marks the current knowledge source unavailable. Empty sources clear
retired entries. Existing models/providers and policy rule semantics are unchanged.

## Explicit upgrade from Chroma 1.5.9

Do not point the new SQLite path at the old Chroma database. The application does
not automatically migrate or delete old indexes. Private startup detects an
existing configured legacy transcript index and requires an explicit migration
marker before proceeding; creating an empty new database does not bypass this.
Use `CHROMA_PERSIST_DIR` to identify a non-default old index during the upgrade.

1. Stop ingestion and all writers in the old installation. Retain a private,
   complete backup of its data, including the original Chroma index directory.
2. Using the old isolated environment with the reviewed Chroma 1.5.9 SDK, run the
   new checkout's exporter. Do not expose this unpatched environment as a service
   or run it on untrusted index files:

   ```bash
   /private/legacy-venv/bin/python -m tools.semantic_migration export /private/old/chroma_db /private/backups/semantic-export.json --confirm-offline
   ```

   The exporter copies the directory into private temporary storage and opens
   only that copy with the old SDK. It exports documents, original IDs and
   metadata for `policy_kb` and `voice_calls`. Unknown collections are an error,
   not silently omitted. This requires a stopped source; the tool does not
   establish an application-wide point-in-time snapshot while writers are active.
3. Using the new runtime environment, create a separate index:

   ```bash
   .venv/bin/python -m tools.semantic_migration import /private/backups/semantic-export.json /private/new-data/semantic/index.sqlite
   ```

   Older defaults can place policies in `/tmp/chroma_db` and transcripts in
   `DATA_DIR/chroma_db`. If those are separate directories, export each while
   stopped and combine the exports in one import:

   ```bash
   .venv/bin/python -m tools.semantic_migration import /private/backups/calls.json /private/new-data/semantic/index.sqlite --additional-source /private/backups/policies.json
   ```

   Repeat `--additional-source` for other reviewed exports. The 256 MiB input
   limit applies to their combined size. Identical records with the same ID are
   imported once; conflicting text or metadata for an ID fails before publication.
   Duplicate keys inside JSON objects are also rejected. Resolve conflicts in
   reviewed copies of the exports rather than overwriting the original indexes.

   The importer validates the format, re-embeds text locally and records the
   export hash and embedding implementation version. It publishes the completed
   database only after import succeeds. Existing destinations are never replaced;
   failed imports leave no published partial index. Imports are bounded to
   256 MiB of JSON and may need additional memory for model and parsed content.
4. Verify counts, IDs, metadata, representative retrieval queries and access
   controls in the new private instance before selecting its `SEMANTIC_DB_PATH`.
   Preserve the old files for rollback until a separate retention decision.

An old knowledge-only index at another path must be exported explicitly too.
The guard cannot discover arbitrary historical directories. Static knowledge and
the editable knowledge store are still used to rebuild active policy chunks.

Deleting a call removes its active indexed call context and STT artifacts before
removing the primary run. Cleanup failures are reported and retain the primary
record for retry. This is not an atomic transaction across all stores; earlier
cleanup steps may have succeeded before a later failure. Archived legacy indexes
and backups retain their own retention obligations and are not erased by the API.

## Limits

Queries perform an exact scan over vectors in the selected namespace. Memory for
ranking is bounded by the requested result count, but query work grows with the
number of stored documents. This is intended for the first private instances,
not a demonstrated high-volume search service. MiniLM is an English-oriented
model with token-length limits; no general multilingual retrieval claim is made.

Embeddings from an incompatible recorded implementation are rejected rather than
silently compared. Re-embedding may change rankings; names and dimensions alone
do not prove equivalent retrieval. The migration acceptance corpus is authored
synthetic data and cannot establish production detection accuracy.

The recorded implementation tag is not a cryptographic fingerprint of model
weights. Keep model assets trusted and immutable. Changing the ONNX model or
tokenizer assets requires a separately verified reindex; changing a configured
local model directory alone is not a supported model-upgrade procedure.

See [candidate verification](release-candidate-verification.md) for executed checks
and remaining release gates.

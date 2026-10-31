# Chroma advisory assessment, October 31, 2026

## Private single-company release follow-up

The release review replaces the old unconditional CVE ignore with a temporary,
version-bound policy in `tools/dependency_audit.py`. This section supersedes the
earlier statement below that no exception exists. The exception is valid only
before **2026-11-07 UTC**, only for **chromadb 1.5.9**, and only for
`PYSEC-2026-311`, `PYSEC-2026-3813`, `PYSEC-2026-3814` and `PYSEC-2026-3815`.
The raw audit currently returns five records because `PYSEC-2026-311` is duplicated.
Its [official record](https://osv.dev/vulnerability/PYSEC-2026-311) describes the
same server collection-configuration boundary as the later code-injection advisory.
The earlier CI CVE ignore covered those two records without a version or expiry.

Both dependency declarations now pin 1.5.9. At this review, PyPI reports 1.5.9
as the latest release and the vulnerability records list no fixed release.
Chroma is used for policy and transcript retrieval, so removing it would remove
working behavior. No architecture change or downgrade is warranted by this review.

`storage/chroma_client.py` now explicitly selects the embedded Rust API and disables
server authentication/authorization providers for both application clients.
Environment settings cannot select a different transport through those clients.
No Chroma server process or collection-configuration endpoint is deployed by the
repository's Docker, Compose or Railway configuration. Regression checks verify
the actual transport, default embedding function and absent server routes. Runtime
inspection in the Python 3.11 image checks listening sockets and exposed routes.

The principal-engineer assessment is **not applicable to the tested embedded-only
private application boundary**, with review due November 7. It does not assert
that ChromaDB itself is patched. The exception must be withdrawn if a Chroma server
is exposed, remote/model configuration is accepted, another version is installed,
or another process accesses the private data volume. Hosted configuration remains
subject to separate verification before deployment.

The audit still scans the complete requirements and fails for unknown advisories,
other packages or versions, a newly available fix, skipped dependencies, invalid
scan output, or expiry. Every accepted exception is printed explicitly. Tests cover
the negative cases. A package upgrade requires reassessment rather than inheriting
this exception. CI must run these tests and the Docker boundary checks before merge.

The remainder records the earlier assessment before runtime enforcement was added.

For today's private demo, the inspected repository does not expose the entry
points described in the three failing ChromaDB advisories. This is a scoped
applicability assessment, not a patch to ChromaDB or a production security sign-off.
The dependency audit remains red. No advisory exception was added.

## What fails

GitHub Actions run `41129339946`, commit `93de868`, fails only its audit job:

```text
chromadb 1.5.9 PYSEC-2026-3814
chromadb 1.5.9 PYSEC-2026-3815
chromadb 1.5.9 PYSEC-2026-3813
```

Tests, frontend, type checking, lint and benchmark passed. Docker was skipped
because its audit dependency failed. Package audits match installed versions;
they do not establish that an application exposes an advisory's entry point.

## Applicability evidence

| Advisory | Prerequisite described by the advisory | Inspected VoiceScope behavior |
| --- | --- | --- |
| [PYSEC-2026-3814](https://osv.dev/vulnerability/PYSEC-2026-3814), CVE-2026-45833 | A Chroma server collection-update request accepts an attacker-selected model repository and `trust_remote_code` configuration. | No Chroma HTTP server is mounted or started. VoiceScope exposes neither collection-update nor embedding-configuration APIs. Policy input accepts text, not model configuration. Both collections use the default embedding function. |
| [PYSEC-2026-3813](https://osv.dev/vulnerability/PYSEC-2026-3813), CVE-2026-45830 | Chroma server authorization fails to enforce tenant ownership. | Both clients are embedded `PersistentClient` instances using `chromadb.api.rust.RustBindingsAPI`. No Chroma server authentication or authorization provider is configured in the tested environment. |
| [PYSEC-2026-3815](https://osv.dev/vulnerability/PYSEC-2026-3815), CVE-2026-45831 | Chroma's `SimpleRBACAuthorizationProvider` authorizes actions without checking their resource scope. | VoiceScope does not configure this provider or use Chroma as its user/tenant authorization service. |

Sources inspected: `core/knowledge_base.py`, `storage/chroma_store.py`,
`api/routes.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `railway.toml`,
and installed ChromaDB 1.5.9 client, settings and server authorization code.
Docker starts `uvicorn main:app`. Compose starts VoiceScope and PostgreSQL;
it does not declare a Chroma service.

## Reproducible checks

`tests/test_chroma_security_boundary.py` adds six checks:

- Instantiate the real embedded collection in temporary storage. Assert the Rust
  API, absent server authorization providers and default embedding function.
- Send authenticated requests to four Chroma server paths, including the
  collection-update path from the code-injection advisory. All return 404.
- Verify that VoiceScope's policy input model discards model configuration and
  tenant fields rather than forwarding them into Chroma configuration.

These are boundary regression tests. They are not exploit attempts and use no
real transcripts, recordings, malicious repositories or executable payloads.
The full backend suite passes 618 tests after adding these six cases. Configured
Ruff and the focused mypy check pass. The frontend was not changed in this pass.
The live local client inspection independently confirmed the same Rust API and
default embedding function. A synthetic collection was created without supplying
documents or sending data to a new provider.

The same inspection inside the non-root Python 3.11 production image confirmed
ChromaDB 1.5.9, the embedded Rust API, no server authorization provider, the default
embedding function, zero new listening sockets after client initialization, and
zero Chroma server paths in VoiceScope's OpenAPI document.

## Limits and deadline decision

Use the private, loopback-only demo today. The inspected entry points do not
justify a last-minute vector-store rewrite or a Chroma downgrade. They also do
not justify calling the installed dependency patched.

The hosted environment remains uninspected because deployment access is unavailable.
`CHROMA_API_IMPL` and other operator-controlled Chroma settings can change client
behavior. The new regression checks fail if the tested configuration selects a
server transport, but they cannot prove an inaccessible deployment has the same
configuration. A separate Chroma service outside this repository is also outside
this assessment.

Calls, policies and ordinary reports remain globally shared behind API-key access.
That independent limitation still prevents a multi-company security claim. Keep
real customer material out of an unrestricted public shared-key demo. Keep the
public STT review proxy disabled.

Before making an audit exception, bind it to a reviewed package version and the
embedded-only deployment conditions, retain the regression checks, and record an
expiry/review requirement. The current open-ended `chromadb>=0.5.0` dependency
would make an unconditional ignore apply to future versions too. This assessment
does not introduce that ignore or authorize a production merge.

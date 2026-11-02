# Public synthetic Preview

The isolated staging frontend can be opened without Basic credentials when all three server-side conditions hold:

- `PUBLIC_SYNTHETIC_DEMO=true`
- `STAGING_DEMO_ONLY=true`
- Vercel sets `VERCEL_ENV=preview`

Only the separate staging project's Preview environment enables these flags. Its BACKEND_URL must point to the separate Render synthetic-only service. Never point this public frontend at a real-data backend. Production ignores the bypass and retains operator authentication. HTTPS, same-origin checks, no-store responses and backend API-key authentication remain in place.

## Read-only backend contract

The Render backend also needs both `STAGING_DEMO_ONLY=true` and `PUBLIC_SYNTHETIC_DEMO=true`. In this mode the backend rejects every POST, PUT, PATCH and DELETE with HTTP 403, including requests carrying a valid operator API key. Only the explicit demo GET/HEAD paths are available; private configuration routes are denied. Browser controls for uploads, deletion, policy changes and STT setup are hidden. The key remains server-side. A frontend flag alone is not backend authorization.

Public startup refuses a data directory containing non-synthetic calls without deleting or modifying those records. Use a separate ephemeral DATA_DIR, no external database and no live provider credentials. This is a public fixture environment, not visitor identity or tenant isolation.

Startup seeds six canonical calls. The older reliability seed route reuses those IDs in synthetic staging. Existing three legacy copies are preserved and identified as earlier copies in the UI. Public callers cannot invoke either seed route. Startup can restore expired synthetic artifacts without generating real references or extending real-recording retention.

Pagination accepts limits 1–200, offset 0–2,147,483,647. Invalid parameters return FastAPI's 422 response before database work. Other paginated lists use the same limit range.

Audio supports one HTTP byte range, suffix/open-ended ranges, 206 and 416. The proxy forwards Range and range response headers. Evidence navigation waits for metadata and seek completion before playing. Invalid times, failed downloads and timeouts surface errors; source changes/unmounts cancel pending seeks.

To restore private frontend access, remove either frontend opt-in flag and redeploy. Existing immutable deployments retain their original environment; retire any public deployment URLs separately if access must be revoked. Outside backend public mode, normal private operations remain available.

The existing hosted demo is not automatically updated by these local fixes. A later approved staging deployment must update the backend code and public-mode environment as well as the frontend. Run the local browser regression with `DEMO_QA_URL`, `DEMO_QA_EVIDENCE`, `PLAYWRIGHT_MODULE` and `CHROME_PATH`; it refuses hosted URLs to avoid mutating shared staging data.

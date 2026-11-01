# Public synthetic Preview

The isolated staging frontend can be opened without Basic credentials when all three server-side conditions hold:

- `PUBLIC_SYNTHETIC_DEMO=true`
- `STAGING_DEMO_ONLY=true`
- Vercel sets `VERCEL_ENV=preview`

Only the separate `voicescope-staging-demo` project's Preview environment enables these flags. Its BACKEND_URL must point to the separate Render synthetic-only service. Never point this public frontend at a real-data backend. Production ignores the bypass and retains operator authentication. HTTPS, same-origin checks, no-store responses and backend API-key authentication remain in place.

The backend key stays server-side. Render's synthetic-only mode rejects live providers, recording downloads, uploads and webhook processing. Public visitors can browse and change the synthetic demo through existing allowed routes, including demo policies. These changes are shared and ephemeral; restarting restores fixture data. This is public demo access, not visitor authentication or a privacy boundary.

To restore private access, remove either opt-in flag from Preview and redeploy. Existing immutable deployments retain their original environment; retire any public deployment URLs separately if access needs to be revoked.

Tests cover both opt-ins, Preview-only enforcement, production fail-closed behavior, and retained HTTPS/origin checks. Hosted public acceptance must use a fresh browser context without credentials.

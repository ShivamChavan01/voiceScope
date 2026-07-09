# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in VoiceScope, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email **shivamrc189@gmail.com** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You should receive a response within 48 hours. We'll work with you to understand and address the issue before any public disclosure.

## Security Measures

VoiceScope includes the following security features:

- **API Key Authentication** — All endpoints require `X-API-Key` header (except health/docs)
- **Rate Limiting** — 60 requests per minute per IP
- **SSRF Protection** — DNS resolution checked against private/link-local ranges
- **HTTPS Enforcement** — Webhook URLs validated to be HTTPS-only
- **Input Validation** — Pydantic models validate all API inputs
- **PII Redaction** — Built-in guardrails detect and redact emails, phone numbers, SSNs, credit cards
- **CORS** — Configurable allowed origins
- **No Secrets in Logs** — Input sanitization prevents key leakage

## Scope

- The core VoiceScope API and pipeline
- Authentication and authorization mechanisms
- Webhook URL validation
- LLM provider API key handling

## Out of Scope

- Frontend deployment security (depends on your hosting)
- Third-party LLM provider security
- Social engineering attacks

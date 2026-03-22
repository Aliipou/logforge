# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: ali.pourrahim@example.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

You will receive a response within 48 hours. If confirmed, a patch will be released within 7 days for critical issues.

## Security Design

- All API inputs validated with Pydantic before reaching Kafka
- PostgreSQL queries use parameterized statements (asyncpg) — no string interpolation
- Rate limiting on all public endpoints (Redis sliding window)
- No secrets in code — all config via environment variables
- Docker containers run as non-root users

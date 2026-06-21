# Security policy

This document describes how we handle **security-sensitive information** for
[WatchTower AI](https://github.com/kaiiiichen/WatchTower-AI) and this repository.

---

## Supported scope

We care about vulnerabilities that affect:

- **The probe engine** (FastAPI backend) when misconfiguration or code flaws could
  leak API keys, expose local diagnostics to unintended callers, or allow
  unauthorized control of probe behavior.
- **The dashboard** (Next.js frontend) when deployed with a public `BACKEND_URL`,
  including proxy routes that forward to the probe engine.
- **Local data** in `backend/data/watchtower.db` when issues stem from this
  application's code or documented deployment practices.
- **Observability** (Sentry) when events or traces could leak provider API keys
  or other secrets before redaction.

We do **not** provide a formal bug bounty program. Reports are handled
**best-effort**.

---

## How to report a vulnerability

**Do not** open a public GitHub issue with exploit details, payloads, or
step-by-step instructions that put other users at risk.

Instead:

1. **Contact the maintainer privately**, using one of:
   - **Email:** [kaichen0728@gmail.com](mailto:kaichen0728@gmail.com), or
   - GitHub **private security advisories** for this repository (if enabled), or
   - A direct message to [@kaiiiichen](https://github.com/kaiiiichen) for
     **non-sensitive** coordination only (not for long exploit write-ups).

2. Include **what component** is affected (e.g. route path, env var, file), **impact**,
   and **minimal reproduction** steps where safe.

3. Allow reasonable time for triage before public disclosure. Coordinated
   disclosure is appreciated.

---

## What we will do

- Acknowledge receipt when possible.
- Investigate and patch or mitigate **critical** issues in production
  configuration or code when they fall within project control.
- Credit reporters in release notes or advisories if they want attribution
  (optional).

---

## Secrets hygiene (for contributors and users)

WatchTower AI is designed as a **local developer tool**: your provider API keys
and probe history stay on your machine.

- **Never commit** `backend/.env`, `frontend/.env.local`, API keys, or
  `backend/data/watchtower.db`.
- If a secret was ever committed — even briefly — **rotate it** in the provider
  (Anthropic, OpenAI, Google, Sentry) and **purge** from git history if the repo
  was public.
- The backend redacts API keys from Sentry payloads (including Gemini `?key=`
  query params). Report gaps in redaction through private channels.
- When deploying the backend publicly, restrict network access and set
  `CORS_ORIGINS` deliberately. The probe engine is not intended as an open
  multi-tenant service.

See also [README.md — Configuration](README.md#configuration) and
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Out of scope (examples)

Reports may be **declined** or redirected when they concern:

- Third-party provider outages or API policy (Anthropic, OpenAI, Google) —
  use their official channels.
- **Social engineering** or account takeover of maintainer accounts outside
  this codebase.
- **Theoretical** issues without a plausible attack path against deployed
  configuration.
- Missing API keys showing a provider as `unknown` — this is expected behavior.

---

## Safe harbor

If you make a **good-faith** effort to avoid privacy violations, data destruction,
or service disruption — and you report issues responsibly — we will not pursue
legal action against you. Do not access data that is not yours, and do not perform
destructive tests on production.

---

## Related documents

- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community behavior.
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to submit code changes.
- [README.md](README.md) — architecture and API overview.

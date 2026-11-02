# Security and Publication Boundaries

ResolveGuard is a synthetic local demonstration. This document is not a production security certification, vulnerability scan, legal assessment or institutional approval.

## Controls retained

Public policies are guest-accessible. Confidential records require backend identity/assurance and applicable resource/action authorization. Delegation is scoped and revocable; family relationships alone grant no rights. The model and browser cannot grant permission. Transaction/case list services still call the protected backend for every record; they do not filter a raw private dataset in the UI.

Fraud/error statements are durably captured without turning receipt into confirmed investigation, legal notice or card action. Idempotency, retries and unknown-state reconciliation remain intact. Simulated emergency card handling requires permitted backend evidence. Transfers, refunds, credential changes, guarantees and official bank integrations remain unavailable.

Runtime reply configuration cannot import cloud settings. Environment parsing is literal, allowlisted and preserves pre-existing process values; it does not interpolate expressions. Provider endpoints and opt-in gates are not loosened. Different hashing functions and redaction layers retain their original purposes.

## Publication review

`.env`, API keys, runtime databases, cookies/tokens, browser profiles, stdout logs and Office lockfiles must stay private/untracked. `.env.example` retains empty credential fields. Do not paste keys, passwords, PINs, CVVs or OTPs into chat. Use fictional data only.

`tools.repository_checks` checks Python syntax and selected high-confidence credential patterns in source/config/docs without printing values. It is not universal PII detection, a Git-history scan, or a vulnerability database audit. `uv pip check` verifies installed dependency metadata compatibility; it does not establish absence of known vulnerabilities. No Git repository existed at audit start, so committed-file/history claims cannot be made.

Historical source copies, prompt fixtures, reports and human feedback are evidence, not automatically unused material. Preserve them; use the artifact classification in [development](DEVELOPMENT.md). Review publication artifacts manually before creating the repository. A license is still unspecified; none is invented here.

## Operational limits

Regex masking, append-only SQLite and polling alerts do not replace production privacy controls, immutable archives, IAM, retention policies or real-time response. Hosted LangSmith, Replit deployment and real banking remain deferred. CI is credential-free, read-only and does not deploy; its [first hosted run](https://github.com/akanshk-cmyk/ResolveGuard-AI/actions/runs/41398641024) passed. This is not a production security certification.

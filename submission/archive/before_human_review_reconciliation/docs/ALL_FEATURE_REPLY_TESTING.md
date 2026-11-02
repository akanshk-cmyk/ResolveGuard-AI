# All-feature live reply testing

User authorized enabling live model responses for all customer-chat features on
October 31, 2026. Mode `RESOLVEGUARD_REPLY_MODE=all` extends the existing constrained
framing mechanism across all nonempty chat reply categories passing the shared QA
boundary: public/archived-bank policies, comparisons, clarification, account
reads, authentication prompts, security refusals, fraud intake, support handoffs,
draft/confirm/cancel case flows and demo callback confirmations.

"All" means model-assisted framing for all these reply categories. It does not
mean unrestricted model-written factual paragraphs, generated permissions,
autonomous financial operations, live bank APIs, production authentication or
real telephone callbacks. Existing actions, sources and factual text are still
constructed and checked locally. System API errors and static page labels are not
LLM responses. Empty/oversized output or provider/validation failure still uses
the controlled fallback; live framing is not guaranteed for every request.

For this mode the provider receives only the reply category and numbered passage
placeholders. It receives no actual factual paragraphs, original customer message,
product source text, transaction details, session identifiers or action receipts.
The model must return every passage ID once in order and select approved
conversational framing. Python inserts the original paragraphs unchanged. The
final QA gate rechecks sources, access and durable action records before delivery.
Sign-in buttons, confirmation controls, cards and action states are not changed.

The existing five-second deadline, per-instance concurrency cap, durable retry
cache, local usage/latency telemetry and fallback remain active. Mode and scope are
visible from `/api/health`; `all_feature_reply_framing=true` confirms configuration,
not successful generation for every request. Inspect each reply's generation
outcome or local reviewer trace for actual success/fallback.

Tests with an intercepted provider cover thirteen reply categories. End-to-end
HTTP tests cover sign-in requirements, security refusal, product comparison,
fraud intake, case draft and explicit confirmation, and the simulated callback.
Private ownership/expiry/step-up tests remain in the suite. Run historical suites
with `RESOLVEGUARD_REPLY_MODE=off` in the test process to avoid unintended paid
requests. Run generation tests with injected settings/providers.

Cloud tracing, deployment and real bank integrations remain excluded. Earlier
human qualification blocks are not cleared by enabling generation.

## Activation verification

The app is configured with `reply_mode=all`. Main regression suite: 289 tests run,
288 pass and one expected skip. Seventeen targeted generation tests pass.

Nine actual Nebius test requests covered authentication, security refusal,
clarification, comparison, private reading, fraud intake, demo callback, case draft
and case confirmation. Eight generated replies passed final validation. Comparison
used the controlled fallback after output truncation. Raising its output allowance
from 512 to 1024 tokens retained the five-second deadline; a separate comparison
retest hit that deadline and again returned the safe fallback. Comparison live
framing is enabled but its reliability under this latency budget remains a known
limitation. No unsupported output was delivered and no failed measurement was
overwritten. Reported usage is now retained for rejected provider responses when
the provider supplies it.

Evidence: `artifacts/public_generation/all_features_live_smoke.json` and
`artifacts/public_generation/comparison_corrected_live_smoke.json`. These are
individual development tests, not a statistically reliable p95 or release score.

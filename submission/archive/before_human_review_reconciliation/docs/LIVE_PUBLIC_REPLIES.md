# Opt-in public reply generation

Implemented October 31, 2026. This is a constrained first release for the synthetic
ResolveGuard demo, not production qualification or unrestricted generative chat.
The user selected **implement and test; leave live replies opt-in**. The real
`.env` was not changed and no paid provider request was made for this change.

## Architecture and rationale

1. The existing customer flow identifies the product and retrieves approved,
   current fictional policy sources. Ambiguous requests still ask for a product.
2. The shared web response boundary checks the controlled answer against the
   current product answer builder. It reserves a durable generation key in a
   short transaction, then closes the transaction before any provider request.
3. A request-scoped LangGraph subgraph runs `generate_reply -> validate_reply`.
   Failed validation branches to `template_fallback`; approved output ends the
   graph. Both outcomes continue through the existing customer QA gate.
4. GLM-5.3-Flash selects a structured opening, the required passage IDs and a
   closing. Python reconstructs the reply from immutable approved paragraphs.
   Missing, duplicate, invented or reordered passages are rejected. The model
   cannot alter fees, waiver conditions, APY tiers, dates or source claims.
5. Final QA independently checks the original policy answer and the generated
   layout. A forged `base_response` is not accepted merely because it appears in
   generation metadata. Current session/time is fetched again after generation.
6. The approved response is returned through the existing JSON interface. The
   interface does not need a new streaming protocol or a new customer workflow.

This is genuine optional provider execution for **conversational framing**, not
free-form model authorship of the factual paragraphs. The allowed wording is
deliberately small. Arbitrary natural paraphrasing remains a separate scope:
numeric matching and a second model's opinion cannot guarantee equivalence of
banking conditions. This implementation does not claim that capability.

The existing account LangGraph and backend authority boundaries are retained.
The new generation subgraph sits at the shared public reply boundary because
public BOW conversations do not all pass through the account graph. Inserting a
node only into the account graph would miss the main public customer journey.

## Scope

Eligible: BOW, public guidance, one selected product, source-backed answer, no
account cards. Public comparisons, archived-bank responses, clarification,
security refusals, authentication prompts, private account explanations and action
confirmations keep their existing controlled wording. Model generation never
executes a banking tool, changes authorization or fabricates a successful action.

Only topic, product ID, approved answer passages and allowlisted public source
fields enter the prompt. Raw customer questions, session identifiers, account
records, conversation history and credentials do not enter it. No customer
conversation is automatically sent to LangSmith. The API key is used only in
the Nebius authorization header.

## Configuration

Default settings are documented in `.env.example`. To enable later, set these in
the project `.env` or process environment and restart the customer server:

```text
RESOLVEGUARD_REPLY_MODE=public
RESOLVEGUARD_REPLY_TIMEOUT=5
RESOLVEGUARD_REPLY_BUDGET_MS=8000
```

An existing `NEBIUS_API_KEY` is required. Missing credentials cause template
fallback, not a secret-bearing error. Set `RESOLVEGUARD_REPLY_MODE=off` and restart
to roll back. Existing process environment values take precedence over `.env`.
Only allowlisted runtime settings are loaded; cloud settings are not enabled.

The endpoint and model are fixed to Nebius Token Factory and
`zai-org/GLM-5.3-Flash`. No cross-provider fallback exists. The provider uses the
[Nebius chat-completions API](https://api.tokenfactory.nebius.com/docs).
JSON parsing and Pydantic validation remain mandatory regardless of provider
format support. Actual model availability and measured latency need a future
explicit live smoke test; the tests here intercept the transport.

## Latency, streaming and recovery

- Blocking delivery: unverified tokens are never streamed to the customer.
- Five-second total provider deadline using cancellation, plus per-I/O timeouts.
  A 64 KiB response limit also bounds returned data.
- Two concurrent provider calls per application instance; excess work falls back
  immediately rather than waiting in an unbounded queue.
- No automatic provider retries. Timeout, capacity, truncation, schema failure,
  unexpected tool output and invalid passage layout retain the original answer.
- Eight seconds is the initial generation budget for telemetry, not a measured
  service commitment. Provider-step p95 and end-to-end chat p95 are separate.
- Cached completed requests reuse their result. A concurrent duplicate receives
  HTTP 409 and can retry the same key. After an interrupted reservation is at
  least 15 seconds old, retry stores the original template without another paid
  request. Recovery never repeats a banking operation.
- Reservations/cache are SQLite-backed. Model execution happens outside its
  transaction. Existing databases receive an additive schema migration.

Future production decisions include load-based budgets, a distributed provider
concurrency/rate limiter, capacity testing and provider outage policies. The local
two-call limit is not a global multi-worker rate limit. Progressive delivery of
an already-approved response is possible later; raw-token streaming would bypass
the current whole-response safety gate.

## Observability

Local traces append `reply.generate` and `reply.validate` spans to existing
retrieval/tool evidence. Generation records include prompt version, evidence hash,
requested/returned model, provider latency, deadline failure, validation outcome,
reported input/output tokens and budget status. Rejected drafts retain known
usage. Unknown tokens/cost remain unknown; no list price is invented.

Request-local usage does not share a mutable provider usage list across requests.
The operations API/dashboard exposes generation sample count, p95, fallbacks and
over-budget observations. Aggregates cover the bounded local observation window,
not all-time production statistics. The model's hidden reasoning is not logged.

Generation metadata has its own `reply_execution_mode=NEBIUS_CONSTRAINED`; the
existing `execution_mode` still describes mock routing/backend behavior. A live
presentation call does not make the entire journey a live-bank workflow.

LangSmith framework auto-export is explicitly suppressed for this subgraph.
LangSmith Cloud, Replit deployment and real bank integrations remain excluded.

## Files and verification

- `resolveguard/reply_generation.py`: settings, provider transport, structured
  draft, constrained rendering and LangGraph orchestration.
- `resolveguard/web.py`: shared response integration, durable request cache and
  final current-session QA.
- `resolveguard/answer_evidence.py`: generated-layout verification followed by
  existing independent exact policy verification.
- `resolveguard/customer_review.py`: append generation spans without replacing
  retrieval/tool history; record minimized local generation observations.
- `resolveguard/telemetry.py`, `monitoring.py`, `dashboard.py`: allowlisted metrics
  and separated generation aggregates.
- `resolveguard/static/operations.html`, `operations.js`: generation panel.
- `tests/test_reply_generation.py`: opt-in/default-off behavior, exact facts,
  output attacks, privacy boundaries, deadline cancellation, capacity, usage,
  HTTP adapter contract, retry cache and crash recovery. All provider calls in
  these tests use a fake provider or HTTP MockTransport, not external networking.

Run with the project's existing Python 3.12 environment:

```powershell
uv run --locked --extra evals python -m unittest discover -s tests -p test_reply_generation.py -v
uv run --locked --extra evals python -m unittest discover -s tests -q
uv run --locked --extra evals python -m unittest discover -s resolveguard_synthetic_v04/tests -q
```

Human reference approvals, sixteen BOW source-contract conflicts and the two
previous semantic scoring flags remain pending. This change does not clear those
qualification blocks or reinterpret earlier mock benchmark scores as live scores.

## Verified implementation results

- Main Python suite: 286 tests run, 285 pass and one expected dependency-branch
  skip. This includes fourteen new generation tests.
- Synthetic-fixture suite: thirteen pass.
- Customer browser: forty-eight checks pass; no browser exceptions.
- Operations browser: eight checks pass, including the new generation panel.
- BOW baseline with generation off: 100/100 local assertions pass. Human approval
  and the sixteen source conflicts remain explicitly pending.
- Original baseline with generation off: 100/100 local assertions pass.
- Reviewer browser: ten checks pass, including scope denial and logout clearing.
- Runtime health confirms `reply_mode=off` and `provider_calls=false` after reload.

The new generation tests exercise an enabled adapter with a fake provider through
the real customer HTTP boundary and final QA, not only isolated helper methods.
They also verify that retrieval traces survive, generation traces are appended,
and reported usage reaches local observations. The real HTTP adapter is tested
with intercepted transport, including cancellation and unsafe provider outputs.
Actual paid provider execution, real token usage and live p95 remain unverified.

The implementation also verifies exact source content against the local catalog
and chunk registry before transmission. A forged PUBLIC/approved tag alone is
insufficient. Existing source and date checks remain in the final QA gate.

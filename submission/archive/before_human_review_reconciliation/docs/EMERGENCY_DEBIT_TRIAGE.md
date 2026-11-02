# Active debit-card theft: local emergency workflow

Implemented for the synthetic ResolveGuard demo on October 31, 2026. Real bank
integration and LangSmith Cloud activation remain excluded. A demo lock never
freezes a real payment card and a demo fraud ticket is not an official bank filing.

## Customer experience

"My debit card was stolen and someone is using it right now" immediately selects
`triage_intent=HIGH_SEVERITY_FRAUD`. The existing broad FRAUD_ERROR_REPORT route is
retained for compatibility; the new high-severity branch runs before the normal
classifier, product clarification, retrieval and generation. It does not wait for
GLM framing, even with global reply mode `all` enabled. Ordinary non-active fraud
reports keep their previous behavior. Hypothetical, negated theft and credit-card
examples do not enter this debit-card action path.

The reply starts with calm, fixed empathy. It does not invent a name, promise an
investigation has started, guarantee reimbursement or promise a refund date.

1. Save the original report first, without requiring sign-in.
2. Verify identity, bank scope, active/open checking-account ownership, service
   permission and card-action authority. Guest/expired/step-up sessions cannot
   lock a card. Existing representative read-only access is not card-lock authority.
3. Identify the affected demo card using the selected account/payment, or the one
   unambiguous owned checking account. Multiple eligible accounts require selection;
   the system does not lock every card or silently choose the first account.
   Third-party card statements do not select the caller's own card automatically.
4. Commit the synthetic card lock, then independently read its durable current
   state. Confirm a lock only when that read returns positive scoped evidence.
5. Retrieve only PENDING payments for the authorized account. Store merchant,
   amount, currency, source date and observation timestamp as review candidates.
   Pending payments are not automatically declared fraudulent. Incomplete retrieval
   is labelled PARTIAL rather than claiming a complete review.
6. Create an idempotent, append-only DEMO-FRAUD intake ticket linked to the report.
   Request the urgent fraud support queue. A lock failure does not erase the
   report; a ticket failure does not roll back a successful protective lock.
7. Recheck receipts, ownership and the exact emergency explanation at the final
   customer QA gate. The UI separately shows demo card protection, fraud intake,
   report, formal notice, investigation and human-support status.

A guest sees secure sign-in and can resume the original request after successful
authentication. The original guest report remains stored. The authenticated
continuation may have its own report receipt; the existing session continuation
links preserve audit history without transferring private permissions or treating
a guest statement as verified consent.

## Synthetic backend policy and evidence

The new adapter represents **one fictional debit card per eligible checking
account**. No card numbers, PANs or CVVs are generated. This mapping is a declared
demo assumption, not a bank card-inventory integration. Bank/account scope and
customer ownership are checked inside the adapter independently of the model.
The only card-writing service is resolveguard-agent; case/transaction read scope
does not establish third-party card-writing permission.

`emergency_cards` records current demo lock state; `emergency_locks` records scoped
lock receipts; `emergency_disputes` stores immutable initial review snapshots and
ticket receipts. These are separate from ordinary support cases and legal notice
acceptance. SQL triggers prohibit application updates/deletes of receipt history.
They are not an independently tamper-proof regulatory archive. Same-request retries
reuse deterministic operation/ticket IDs. Cross-account selection, revoked access
and mismatched bank IDs cannot retrieve another account's action receipt.

The fixture ledger supplies dates, not precise payment-event timestamps. Tickets
explicitly record SOURCE_DATE_ONLY and observed_at; midnight timestamps or live
bank ledger freshness are not invented.

Faults include card_lock_timeout, card_lock_commit_then_timeout, card_state_timeout
and fraud_dispute_timeout. A lost acknowledgement can be reconciled only by an
authorized positive state read. Timeout/malformed/denied state reads produce an
unconfirmed lock message and urgent support routing. No LLM can rewrite that claim.

## Regulatory disclosure boundary

No approved bank-specific provisional-credit/investigation timeline text was
provided for this feature. The reply states that those terms need confirmation
from support and that no refund amount/date is guaranteed. It does not present
that source gap as a complete regulatory disclosure or compliance approval.

[CFPB Regulation E section 1005.11](https://www.consumerfinance.gov/rules-policy/regulations/1005/11/)
is a reference for later policy review; its conditional requirements are not
silently converted into universal promises, bank-approved wording or a legal
notice-acceptance decision. Production needs approved jurisdiction/account-specific
disclosures and real bank fraud intake integration.

## Traces and privacy

Local traces include the trigger timestamp, deterministic version, nested tool
steps, masked parameters, response status, current card verification and composed
reply. The approved-for-transport response is also recorded after QA; it is not a
claim that the customer received or read the reply. Existing reviewer evidence
links report receipts, access decisions and the actual approved response.

Original customer statements stay in protected local intake storage. Traces use
statement hashes rather than raw secret-containing statements. Account/session
identifiers and full card numbers, PINs, CVVs and OTPs are masked. Sensitive details
are never requested in chat. The emergency path makes no model calls.

The existing dual opt-in LangSmith exporter can receive execution structure and
allowlisted emergency statuses/timestamps. Its privacy projection deliberately
excludes raw tool payloads and customer text; detailed masked evidence stays local.
Cloud export remains OFF and no hosted emergency trace verification is claimed.
This preserves the earlier cloud exclusion instead of enabling external logging
merely because a new workflow was added.

## Implementation and checks

- fraud_triage.py: detector, Pydantic action results, synthetic adapter, deterministic
  orchestration, evidence verification and customer wording.
- web.py: immediate interception, secure continuation, generation bypass and final
  delivery telemetry. workflow.py also intercepts direct workflow entry; conversation.py
  avoids guessing the first account for an emergency.
- customer_review.py: validates emergency claims against current backend evidence.
- static/app.js: separate emergency protection/ticket status display.
- cloud_privacy.py: bounded emergency event-name and status projection.

Fifteen targeted tests cover detection, lock/ticket idempotency, timeouts, lost
acknowledgements, malformed responses, forged receipts, wrong-account/service/role
denials, multiple-account ambiguity, BOW ownership, pending-record isolation,
guest sign-in/resume, injection, conflicting retry payloads and privacy. They also
verify that backend-proven numeric reference IDs do not cause false PAN alarms,
while an exposed standalone PAN is still blocked. Run with the single project .venv:

```powershell
$env:RESOLVEGUARD_REPLY_MODE='off'
uv run --locked --extra evals python -m unittest discover -s tests -p test_fraud_triage.py -v
```

Against the running local app, `python -m tools.check_emergency_flow` exercises a
guest BOW report and authenticated continuation using synthetic records only.
It makes no model calls and cannot freeze a real bank card. Real card inventory,
provider deadlines/circuit breakers, authorized legal representatives, official
dispute acknowledgements and approved regulatory disclosures require a separately
reviewed real-bank adapter; the demo does not claim those integrations exist.

## Final verification

Main suite: 304 tests run, 303 pass and one expected dependency-branch skip.
All thirteen synthetic-fixture tests pass. Seven dedicated browser checks pass
with no browser errors, including emergency wording, separate lock/ticket status,
guest sign-in, model bypass and protected-data clearing on sign-out.

The running BOW web flow was exercised from guest report through secure sample
sign-in/resume. Both the scoped demo lock and fraud intake ticket were confirmed.
Individual HTTP timings were 377.74 ms for guest intake and 446.46 ms for the
authenticated continuation; these are not p95 estimates or real bank latency.
Evidence is in `artifacts/emergency_triage/live_local_smoke.json` and
`artifacts/emergency_triage/browser_checks.json`.

The ordinary all-feature framing setting remains enabled; emergency replies
intentionally bypass it. Earlier 100-case benchmark results predate this emergency
feature and are not evidence of its release qualification. New emergency behavior
is covered by the dedicated tests; independent reference approval remains separate.

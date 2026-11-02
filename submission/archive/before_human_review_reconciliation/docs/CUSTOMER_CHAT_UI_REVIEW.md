# Customer Chat UI implementation review

Historical review: the gap table below predates the implemented UI updates. Use
the [October 31 alignment review](IMPLEMENTATION_ALIGNMENT_REVIEW.md) for current
implementation status, test evidence and prioritized remaining work.

Review date: October 30, 2026 (America/Los_Angeles).

Implementation update: the customer UI has now been updated with service navigation, scoped payment/case pagination, cards, exact USD formatting, independent report/support states, demo verification and expiry cleanup. This original gap table records the pre-update review; see [LOCAL_DEMO.md](../LOCAL_DEMO.md) for the current implementation and verification limits. Real IAM, institution-approved masking, full accessibility evaluation and production controls remain outstanding.

Scope at the time of the initial review: comparison of the [user-supplied UX specification](CUSTOMER_CHAT_UI_SPEC.md) with the then-current local synthetic application. This historical review predates later browser checks; those checks still do not constitute a full accessibility assessment or institutional approval.

## Overall alignment

The proposal matches ResolveGuard's checking/debit support scope, plain language, authorised reads, separate report/case/handoff outcomes and avoidance of credential collection in chat. The current app implements parts of these behaviours but does not yet satisfy the full specification.

| Requirement | Current implementation | Remaining work |
| --- | --- | --- |
| UI-FR-01: Grounded explanations | Backend-scoped transaction reads and date/product/jurisdiction-filtered local policy retrieval exist | Link the displayed explanation to the exact applicable policy version and account terms. Citation presence does not establish relevance. Customer summaries currently map by document ID and need version-aware review. |
| UI-FR-02: Authentication | Sample sessions, permissions and simulated additional-verification checks exist | Implement a trusted sign-in/step-up integration or clearly labelled demo adapter, explicit UI states and cancellation/failure handling. Do not display a real secure-session assurance for fixture selection. |
| UI-FR-03: Fraud/error capture | Durable report capture is separate from case creation and support delivery | Render all five independent backend statuses, with unknown/not-applicable states. Do not derive a combined success indicator from one field. |
| UI-FR-04: Case submission | Saved drafts, explicit confirmation, durable commit and retry/reconciliation paths exist | Add structured case/status cards and clear unconfirmed-state recovery. A response timeout must not enable an unrelated duplicate submission. |
| UI-FR-05: Financial formatting | Integer cents and USD-only transaction contracts exist | Replace floating-point display conversion with integer/decimal-safe formatting, preserve actual status meanings and define direction. Current records do not provide a separate debit/credit field; do not infer a debit sign merely from a positive amount or a pending status. |
| UI-FR-06: Authorisation | Backend checks scope before returning transaction/case records | Keep UI fields on an explicit allowlist; add compact authorised cards, pagination and neutral access-denial tests. Do not invent masked account/card digits absent from backend data. |
| UI-FR-07: Human support | Acknowledged, unavailable, blocked and unknown outcomes are distinguished | Add requested/pending/confirmed visual states where supported by real events. Do not invent intermediate progress, team availability or wait times. |
| UI-FR-08: Data protection | Customer API excludes internal traces/model context; basic trace sanitisation exists | Formalise field-level masking, sensitive-input handling, expiry cleanup and browser privacy tests. Excluding a value from display alone is insufficient if it remains accessible in the page state. |
| UI-FR-09: Adversarial resilience | Strict contracts, backend permissions and a basic policy-injection filter exist | Add UI-focused adversarial tests. Current filtering is not comprehensive prompt-injection protection. |
| UI-FR-10: Session recovery | Bound conversations, saved drafts and access rechecks on restored responses exist | Explicit expiry/revocation UI handling must clear restricted cards and transient browser state. Define how expiry is detected during an idle open page and while responses are in flight. |

## Interpretations to preserve

- Treat customer-facing states as a view over independent backend outcomes, not as a single replacement for all workflow state. Report saved and support unavailable can both be true.
- Classify the request before choosing a workflow; authenticate and authorise before disclosing account-specific facts. Recording an unverified complaint may happen independently of restricted reads.
- Keep PUBLIC_GUIDANCE available without claiming knowledge of an individual's account.
- Additional-verification proof must come from the trusted backend, never a typed statement or a client flag.
- Use "Posted" or a reviewed equivalent that preserves the actual transaction meaning; "completed" must not imply irrevocable settlement or a resolved dispute.
- The current MVP accepts USD only. Currency-specific fractional units apply if scope is expanded; do not imply multi-currency support now.
- Render only dates actually supplied. A posting date is not a purchase date; label pending-record dates carefully when fixture naming is ambiguous.
- Never derive account last-four digits from internal IDs such as ACC-001. Add an authorised display field through a validated contract if required.
- Account information can be read-only while reporting and support submission remain write operations.
- A captured report must not wait for case confirmation merely to fit a UI example. Show the actual authoritative report state.
- A trusted alternate contact pathway must be configured before displaying it. Do not invent phone numbers, links or response estimates.
- Do not label customer-facing policy paraphrases as human-approved when approval has not been recorded.

## Delivery order

1. Define Pydantic customer-view contracts and state mapping, including independent reporting states and absent/unknown values.
2. Correct money/date/status presentation and add explicit direction/display-field provenance. Use existing USD fixtures; extend fixture contracts only where new fields are required.
3. Implement clearly labelled demo sign-in/step-up states and restricted-view clearing. A real provider remains a separate integration.
4. Add authorised transaction and case cards, pagination, concise quick actions and support-home navigation.
5. Add report/case/handoff status components and safe reconciliation actions.
6. Verify keyboard/focus/screen-reader behaviour, expiry/revocation, leakage and exact-value formatting with dedicated UI tests.
7. Record exact customer-visible responses and state transitions for the [Agent Review Admin](AGENT_REVIEW_ADMIN_SPEC.md), with privacy controls and correlation IDs.

## Evaluation and approval boundaries

The attachment's RG case-range mappings are proposed coverage, not proof of executed UI tests. The current development set contains 40 selected draft cases from the wider 100-case source suite; some referenced IDs are outside that subset. No claim is made that all 100 scenarios or all visible transitions have passed.

Add dedicated tests for exact cents (including integer boundaries), unsupported currencies, debit/credit direction, unknown dates, unauthorised account references, expired sessions, step-up cancellation, stale asynchronous responses, duplicate submissions and assistive-technology interactions. Preserve existing expected outcomes unless separately reviewed.

Institution-owned decisions remain: approved display fields and masking, identity provider and assurance rules, policy applicability, regulatory wording, alternate support channels and retention. The screenshots and supplied examples are design references, not evidence of these integrations.

## Code reviewed

- `resolveguard/static/index.html` and `app.js`: current customer interface and formatting.
- `resolveguard/web.py`: scoped customer endpoints and restored conversations.
- `resolveguard/presentation.py`: plain-language rendering and policy paraphrases.
- `resolveguard/contracts.py`: USD transaction contract and strict input/output schemas.
- Existing workflow/backend/conversation components described in the project README.

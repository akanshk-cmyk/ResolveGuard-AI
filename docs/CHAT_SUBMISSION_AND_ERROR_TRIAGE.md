# Message submission and payment-error triage fix

The reported phrase `selected charge is incorrectly applied` was not recognized
by the rule-based router, so it fell through to transaction inquiry. Shared
`asserted_payment_error` detection now handles this and related actual-error
assertions. Definitions, reporting instructions and explicit negations do not by
themselves trigger this new detector. Existing fraud/error patterns retain priority.

The workflow also applies the detector after model classification and during the
unavailable/invalid-model fallback. It records `ASSERTED_PAYMENT_ERROR` as an
observable safety-rule event. Trusted saved-case confirmation retains its separate
case-submission path. The optional Nebius routing prompt is versioned as v3;
customer chat remains on its existing local mock model.

Error intake preserves the original statement before restricted reads. A signed-out
customer can save a report; viewing a selected private payment may then require
sign-in. Saving a report does not establish fraud, start an investigation or issue
a refund. Retrying the same request keeps the saved report/handoff identifiers.

The composer now submits on Enter and retains Shift+Enter for a newline. IME
composition is not submitted. A busy submit does not clear the next draft; a failed
preflight restores text without overwriting any newer draft. HTTP requests have a
30-second timeout. A timed-out chat retains its pending request and retry key;
automatic retry never creates a new request identifier.

Verification includes the exact complaint, related error phrases, general-query
and negation controls, model misrouting and failure, signed-in consecutive turns,
guest intake before authentication, and durable retry identifiers. Browser tests
use actual keyboard events and simulated held/timed-out requests, in addition to
existing product, authentication, permission, report and case flows.

Results: 217 application tests (one skipped), 13 original fixture tests, and 46
browser checks passed. The 40-case mock benchmark retains 100% intent accuracy,
100% fraud/error recall and 97.5% journey pass, with its existing policy-evidence
failure. Artifacts: `artifacts/payment_error_eval_001/` and
`artifacts/customer_ui_validation/browser_checks.json`.

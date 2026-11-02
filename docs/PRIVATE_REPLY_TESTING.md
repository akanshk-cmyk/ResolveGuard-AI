# Private reply testing

The user authorized enabling private-account replies for synthetic testing.
Set `RESOLVEGUARD_REPLY_MODE=public_private` and restart the customer app.

This extends the existing constrained framing model to read-only transaction and
existing-case explanations. It does not enable unrestricted private paraphrasing,
balances, financial actions or generated success confirmations.

Before generation or cached-answer use, the server requires a verified session,
re-reads every resource using the current identity and checks that the displayed
cards and original explanation exactly match those authorized records. Mixed
report/action/receipt responses remain deterministic. The final QA gate then
rechecks permissions and reconstructs the private explanation after generation.
Session expiry or cross-account denial cannot be overridden by the model.

Nebius receives only a generic ACCOUNT_READ topic and numbered placeholders.
Amounts, merchant names, dates, case IDs, account references, source details,
customer statements and session identifiers are not transmitted for private
generation. Actual authorized facts are inserted locally, unchanged. The model
can choose only approved openings/closings and must preserve all passage IDs.
Timeouts or rejected drafts use the existing explanation.

Generation metadata identifies `data_scope=PRIVATE_READ`. Local reviewer evidence
and cached replies contain protected sample wording, under the existing staff
permissions and privacy masking. This does not enable external tracing.

To test, open customer chat, sign in with a demo customer, select an owned payment
and ask "Show this transaction." Review generation evidence in the local Agent
Review Admin workspace. A signed-out request must ask for sign-in; another
customer's transaction must remain inaccessible. Public framing remains enabled.

Regression commands should explicitly set `RESOLVEGUARD_REPLY_MODE=off` in the
test process so broad historical suites do not make unintended provider calls.
The generation tests inject their own enabled settings and intercepted providers.

Verification: main suite 287 tests run (286 pass, one expected skip); thirteen
fixture tests pass. The fifteen targeted generation tests include private
ownership, guest, expiry and step-up checks. A live BOW customer transaction-read
test passed final QA with GLM-5.3-Flash in 2,481 ms, reporting 313 input and 246
output tokens. That single measurement is not a p95 estimate. Evidence is saved
in `artifacts/public_generation/private_live_smoke.json`; repeat explicitly with
`uv run --extra evals python -m tools.check_private_live_reply` (paid API call).

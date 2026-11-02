# Guest-first support and sign-in on demand

Implemented for the local synthetic demo on October 30, 2026 (America/Los_Angeles).

Update: the [BOW workbook integration](BOW_DATA_INTEGRATION.md) now provides product-specific fictional rates and isolated BOW fixtures. The no-rate configuration described below still applies to the separately selectable original demo and to real bank offers; it no longer describes the BOW source.

## Customer experience

New browser sessions start as Guest. Creating an anonymous browser session does not authenticate a customer. Public service navigation and questions do not open a sign-in dialog. The header offers an optional Sign In action.

Public fee, waiver, pending/posted and other explicitly allowlisted sample guidance are answered without customer-record reads. Sources include versions, effective dates and the sample-policy limitation. Internal operating policies are not automatically treated as public content.

Legitimate protected requests show the exact message: "Please sign in securely to view your account details." Explicit security-bypass requests are blocked before saving a sign-in continuation; see [security-aware routing](ADVERSARIAL_ROUTING.md). A Sign In button opens a clearly labelled demo authentication adapter. No real bank identity provider or approved bank redirect has been configured. No password, PIN, CVV or OTP is requested in chat or in the sample sign-in dialog.

The selected original request is stored server-side for 15 minutes and bound to the originating browser. After the explicit demo sign-in, the browser cookie rotates and the request is bound to the new session. The resume endpoint accepts the opaque saved-request reference, not a replacement message. Permissions are checked under the newly signed-in identity before protected data is fetched.

Additional demo verification blocks protected resumption until its backend result succeeds. Cancelling sign-in removes that continuation and leaves public chat available. Cancelling the additional check leaves protected data hidden and public questions available. Existing draft confirmations are not migrated across identities: the customer must review a new authorised draft after reauthentication.

On sign-out, expiry or a detected session change, private messages/cards, selections, drafts and pending in-flight display state are cleared. Public messages stay visible. Asynchronous results from the prior observed session are discarded. Access is checked on focus, every ten seconds while visible, and before displaying responses. This polling is not a production push-revocation guarantee.

Earlier browser sessions from before this experience were introduced are invalidated once through the experience-version check, preventing the old automatic Customer One sign-in from silently surviving the change.

## Public information and published rates

Existing fees and limits remain synthetic test assumptions, not real bank offers. The app only uses a small explicit allowlist of customer-safe policy documents and does not search all internal policies for guest answers. Unknown topics receive a source-unavailable response rather than a fabricated answer or an unnecessary sign-in demand.

`data/public_rates.json` contains an empty published-rate list because no approved current bank rate sheet was supplied. The rate-answer path supports a validated, server-configured product, APY, source HTTPS URL, version, effective date, optional expiry and publication status. Only a single applicable current source is used. Missing, future, expired, invalid or conflicting records do not produce a quoted rate. Synthetic test rates are explicitly identified as fictional.

The rate-source capability is implemented and tested using an isolated test fixture. The live savings-rate acceptance criterion remains dependent on a real approved published source. No test rate was added as a real bank offer.

## Account information

- A spouse, parent, child, family member or friend gains no access from the
  relationship or a consent claim typed into chat. Backend-verified identity and
  explicit authorized resource/action scope are required. Validated legal
  delegation allows only its recorded scope, and revocation is rechecked.
- Personal fees, payment details/history, balances, personal account information and support-case requests require adequate sign-in/verification before protected lookup.
- Current backend customer, account, delegation and service permissions remain authoritative after sign-in. Sign-in never grants another customer's account access.
- Recent-payment requests use permitted records only. Ambiguous personal charges offer authorised candidate payments; the assistant does not guess which charge was intended.
- Balance values are outside the current fixture/API scope. After authentication, the app explains that balances are unavailable rather than inventing a value.
- Existing support cases are listed only through backend-scoped reads. Case submission still requires explicit draft confirmation.

## Reporting before sign-in

Potential fraud/error reports are captured through the existing validated durable intake backend before any protected transaction lookup. The original statement and supplied transaction references are preserved. Report capture, formal-notice review, verification, investigation and support delivery remain distinct.

If a guest also requests selected payment details, the saved continuation resumes only that lookup after sign-in. It does not submit the report again. Reports with no private lookup request do not require sign-in. A saved report does not confirm fraud, a refund, a blocked card or an investigation.

## API responsibilities

| Endpoint | Responsibility |
| --- | --- |
| `POST /api/session` | Start a guest session by default; explicit sample profiles remain available through demo controls |
| `POST /api/chat` | Route public evidence, protected requests and report intake without allowing model output to grant access |
| `GET /api/session` | Return current demo access and the browser's unexpired pending-request reference |
| `POST /api/auth/demo-sign-in` | Explicit demo identity selection, cookie rotation and continuation binding |
| `POST /api/auth/resume` | Revalidate access and execute the unchanged saved request under the new identity |
| `POST /api/auth/cancel` | Remove the permitted continuation without deleting a report |
| `POST /api/session/verification` | Simulate additional verification; never real identity proof |

The original protected request and continuation metadata are stored locally in `web_auth_requests`. Browser cookies and bindings must not be included in review exports. This remains demo SQLite persistence, not production encrypted identity or evidence storage.

## Acceptance and evidence

| Requested behaviour | Verification |
| --- | --- |
| Default signed out; no automatic authentication | API and real browser checks |
| Public monthly fee without sign-in | Sample policy answer, sources and zero customer-record tool calls |
| Personal $12 charge prompts sign-in | Exact prompt; no protected tool reads before authentication |
| Public savings rate without sign-in | Configured-source path tested; real source absent and honestly reported |
| Recent payments require sign-in | Guest gate and automatic authorised resumption tested |
| Original request resumes | Durable continuation, cookie rotation and restart tests |
| Wrong-account access denied after sign-in | Negative authorisation test |
| Sign-in cancelled; public chat available | API and real browser checks |
| Additional verification enforced | Success/cancellation tests and browser playback |
| Reports not delayed or duplicated | Original statement/selectors and event-count tests |
| Expiry removes private views | Browser test with a delayed response |

Tests: `tests/test_guest_first.py`, existing web/presentation/backend tests and `tools/check_customer_ui.py`. Browser evidence is in `artifacts/customer_ui_validation/`. This does not constitute a full accessibility audit or a real IAM integration test.

## Remaining external dependencies

Before replacing the sample adapter, connect the institution-approved authentication and risk-verification provider, validate its callback/session protections and field-level entitlements, and configure approved current public product/rate sources. Production retention, encrypted storage and review permissions remain separate controls. No live authentication integration, external publication, cloud upload or bank data access was performed by this change.

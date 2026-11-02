# Customer Chat UI Feature Specification

## Human review receipt and integration status

Human feedback **was provided and recorded twice**: in chat (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and in the returned Excel workbook (28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). These sets overlap and must not be added into 50 independent tests.

Receipt references: HR-CHAT-22 (`artifacts/human_feedback_20261101_batch02/Review_Summary.json`) and HR-XLSX-28 (`artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json`). The original returned workbook SHA-256 is `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`.

The reviewer confirmed "I tested the live app" and clarified that another customer's case was not shown; three partial passes concern denial wording. Two product-context failures remain reported. Feedback receipt and documentation integration are complete; implementing or accepting every feedback item is not implied.

Human-judge agreement is **not yet calculated on matched responses**: the human reviewed live replies while the judge graded different saved responses. This is not missing human feedback. Formal source-contract approval and exact-saved-response calibration are separate outstanding decisions. No agreement percentage is invented.

This confirms handover of human review feedback to the project record, **not** a bank-support handoff, callback, or operational acknowledgement. Those require separate backend evidence.


Status: Preserved user-supplied proposed UX specification v1.0. Requirements are partly implemented; see the [current alignment review](IMPLEMENTATION_ALIGNMENT_REVIEW.md). Institutional approvals remain pending. The original supplied specification below is unchanged.

Added: October 30, 2026 (America/Los_Angeles).

Source: attached Pasted text.txt, attachment 10d113a3-6eab-46e6-a9ef-2d0290a9213c.

Source SHA-256: `e10ccb325e809094d055ad020d8b305d961ba5ff7532a549c1b024c7736b7778`.

The supplied text is preserved below. Plain-text tables and screen examples reflect the pasted source. See [implementation review](CUSTOMER_CHAT_UI_REVIEW.md) for current gaps and interpretation. This document does not activate banking authentication or approve policy/masking rules.

---

ResolveGuard AI — Customer Chat UI Feature Specifications
UX Specification v1.0
Aligned to PRD v0.4
Customer-Facing Banking Chat

1. Product and UX direction
ResolveGuard should combine the simplicity of the banking chatbot shown in your screenshots with stronger authentication, transactional transparency, case tracking, and customer-protection controls.

The screenshots establish a useful interaction pattern: service-category buttons, nested choices, conversational messages, authentication entry points, and navigation back to the main menu.

However, some behaviors should be redesigned for ResolveGuard.
Screenshot pattern	ResolveGuard recommendation	Rationale
Service categories such as Account, Cards, and My Request	Retain quick-action cards for supported checking/debit-card servicing	Help customers discover services
Multiple successive questions before providing assistance	Ask only information essential to the workflow	Reduce abandonment and unnecessary collection
Customer ID and registered mobile number requests	Route authentication through the bank's approved secure interface	Prevent sensitive credentials from entering chat transcripts
Investment and retail-loan menus	Exclude from the initial MVP	Maintain PRD v0.4 scope
Informational replies containing promotional content	Prioritize verified facts, source information, and next steps	Separate servicing from product marketing
Generic FAQ and back-to-menu controls	Retain, with visible human assistance and case tracking	Improve navigation and recovery

Key UX principle: The assistant must always make clear the difference between understanding a request, verifying a customer, recording a report, creating a case, and resolving an issue.

These are different operational states and must never be represented by the same generic success message.
2. Proposed customer chat layout

ResolveGuard AI

Banking Support Assistant


 Secure session


Hello! I can help explain transactions, answer account-policy questions, report an issue, or check an existing case.

What would you like help with?

Account & Fees


Debit Card


Report an Issue


Track My Case



 Account information is read-only

Human support available



How can I help you?



Conceptual screen specification, not a connected banking interface. The actual secure-session indicator must derive from the bank's authentication service.3. Response behaviors and message flow
The chat UI should implement a finite set of customer-visible states. Each state is driven by a trusted workflow result.
3.1 Chat response state contracts
State	What the customer sees	Required UI behavior
PUBLIC_GUIDANCE	General policy or support guidance	No private account details
AUTH_REQUIRED	"Sign in securely to view your account information."	Open approved authentication flow
STEP_UP_REQUIRED	"Additional verification is required to continue."	Launch trusted verification interface
VERIFICATION_PENDING	"We're checking your verification status."	No restricted action until confirmed
AUTHORIZED_READ	Transaction/case card with permissible fields	Display only backend-authorized information
CLARIFICATION_REQUIRED	Concise question and selection options	Avoid guessing accounts or transactions
REPORT_CAPTURED	Confirmation that a report was recorded	Distinguish capture from formal case creation
CASE_CREATED	Confirmed case ID and current status	Only after committed backend success
SUBMISSION_UNCONFIRMED	"We can't confirm whether your submission was received."	Reconcile rather than blindly resubmit
HANDOFF_PENDING	"We're connecting you with support."	Clearly mark transfer as pending
HANDOFF_CONFIRMED	Receiving team, reference ID, known next step	Only after destination acknowledges handoff
SERVICE_UNAVAILABLE	Clear limitation and approved alternate channel	Never fabricate success, queue time, or status
SESSION_EXPIRED	Secure reauthentication prompt	Hide restricted cards and clear sensitive view state

3.2 Example: fee inquiry
Why did I get a $12 monthly service fee?

Your checking account shows a $12 monthly service fee posted on October 20, 2026.

The applicable fee schedule describes when this fee may apply and the conditions for a waiver.
Transaction details

Description

Monthly service fee

Posted

Oct 20, 2026

Amount

−$12.00

Account

Checking ••0012


Source: Applicable checking fee schedule · Transaction record
Explain waiver rules
Report a fee issue



Illustrative data only. Actual fees, posting dates, account digits, and policy references must come from authorized banking systems and approved evidence.Acceptance criteria — UI-FR-01: A fee explanation may display a specific charge only when the account and transaction have been authorized, the transaction comes from the backend, and the cited policy applies to that account and date.
3.3 Example: step-up authentication
Additional verification required

Before I can show restricted information about this account, please complete verification using the bank's secure process.
Review secure verification design No passwords, one-time codes, PINs, or full card numbers should be requested inside the chat conversation.

The above control requests a design explanation; it is not a real verification action.

UI-FR-02: On step-up success, the backend must issue an updated authorization decision. On failure, expiry, cancellation, or revocation, restricted data remains hidden. The UI must not treat user-entered "Verified" text as proof of authentication.
3.4 Example: potential fraud/error report
If the customer says:
"I don't recognize this $450 debit-card charge."

The assistant should acknowledge the concern and initiate an approved reporting workflow without promising reimbursement or asserting fraud is proven.
Possible unauthorized transaction

I can help you report this transaction and find the appropriate support team.

You said you don't recognize a $450 debit-card charge. I haven't determined whether it was unauthorized.
Report status
Awaiting confirmation

The submission has not yet been confirmed by the reporting system.

If your card may be compromised, use the bank's approved urgent card-support pathway.


UI-FR-03: The UI must represent at least five independent backend statuses: report captured, legal notice determination, identity verification, investigation state, and customer confirmation. The customer-facing wording must not equate a captured message with a formally created case.
3.5 Example: verified case creation
Your support case was created

Case IDCASE-A101

Status
Open

Assigned team

Customer Support

Next step

Await an official case update


Example display only. These fields may appear only after verified backend confirmation.
UI-FR-04: Case-success wording is prohibited unless a committed case ID is present in the authoritative backend result. On timeout or unknown outcome, display an unconfirmed state and provide reconciliation or a safe fallback.
3.6 Example: human handoff
The interface should distinguish requesting support from successfully transferring the conversation.
Stage	Customer message	Visual status
Requested	"I'll request help from a support specialist."	Requested
Routing	"Your request is being routed."	Pending
Confirmed	"Your request was received by the support team."	Confirmed
Unavailable	"We couldn't complete the transfer through chat."	Unavailable

Only show a wait estimate when supplied by an authoritative queue service. Do not invent a human agent's name, acceptance, or availability.

4. Transaction and account data presentation
4.1 Field-level display contract
This is my proposed MVP disclosure policy. The institution's IAM, Privacy, and Security teams must approve the exact fields and masking standards.
Data field	Customer UI rule	Required control
Customer full name	Optional; minimize, especially on shared screens	Authenticated customer and approved display scope
Customer ID	Mask by default; avoid full identifier in chat	Use opaque backend identifier
Account number	Last four digits only, if authorized	Server-side masking
Debit card number	Last four digits only; never full PAN	Card-data security controls
CVV, PIN, OTP, password	Never display or request in chat	Deny and sanitize
Account type	Show where authorized	Account entitlement
Account balance	Outside initial support MVP unless separately approved	Explicit balance permission
Transaction ID	Prefer opaque or shortened display reference	Verified ownership, no enumeration
Merchant / descriptor	Show approved normalized value	Authorized transaction record
Transaction amount	Show currency and two decimal places	Exact backend value
Transaction date	Show posting date and transaction date distinctly when available	Correct date provenance
Transaction status	Pending, posted, reversed, etc., as returned	Backend-derived status
Case ID	Show authorized reference	Case ownership verification
Case status	Show canonical customer-facing status	Authoritative case API
Employee or fraud analyst details	Do not reveal internal-only identifiers	Role-based redaction

4.2 Currency formatting
Your synthetic banking tools store amounts using integer cents. The UI should convert amounts to standard currency notation without modifying the financial value.
Example transaction formatting
Backend amount_cents	45000
Currency code	USD
Displayed amount	$450.00
Debit display	−$450.00


UI-FR-05: The amount display must use a decimal-safe conversion, obey currency-specific fractional units, and distinguish debit/credit direction from transaction status. The LLM must not independently compute or rewrite financial amounts.
4.3 Transaction card rules
The chat should show a compact transaction card for a selected, authorized transaction, rather than exposing entire account histories unnecessarily.

For ambiguous requests, show a permitted selection list with minimal information, such as merchant, date, amount, and masked account reference. Limit the number of transactions visible at once and support pagination.

If the customer does not have access to a requested transaction, the UI should give a neutral access-limitation message without confirming another customer's record exists.

5. Guardrails and visual state indicators
The UI should make security and process states visible without giving misleading assurance.
Indicator	Trigger	Design behavior
Verified	Trusted authentication result	Indicates verified session or action-specific assurance, not global authority
Verification needed	Backend requires step-up	Sensitive information remains hidden
Read-only	Account information lookup	Explains that the chat is not changing account data
Awaiting confirmation	Submission state unknown	Prevents false completion claims
Case created	Backend commit verified	Display reference ID
Under review	Verified case state	State-specific explanation
Service unavailable	API or queue failure	Approved recovery options
Session expired	Authentication invalidated	Hide restricted data and require reauthentication

The Read-only label should apply specifically to account-information access, not to the entire product, because ResolveGuard can submit approved support requests.

A secure-session label must also avoid implying that every requested operation is authorized or that the conversation is immune to account takeover.
6. Navigation, interaction, and accessibility
Following the reference screenshots, I recommend clear service navigation, but with fewer nested menus.

The chat should always support Back to Support Home, View My Cases, and Human Support, subject to channel availability. Customers should be able to enter free text rather than being forced through service buttons.

Accessibility requirements should include keyboard navigation, appropriate screen-reader announcements for new messages, descriptive status text in addition to colors, visible focus indicators, and accessible authentication handoffs.

For multilingual support, do not expose languages that have not been evaluated for financial terminology, fraud recognition, and customer communications. The initial MVP can remain English-only.
7. UI acceptance criteria and evaluation traceability
UI requirement	Evaluation coverage	Acceptance condition
UI-FR-01: Grounded explanations	RG-001–018	Only approved policy and authorized transaction data rendered
UI-FR-02: Authentication	RG-061–070	Restricted view hidden when assurance is insufficient
UI-FR-03: Fraud/error capture	RG-019–033, RG-079–092	Safe wording and independently verified report states
UI-FR-04: Case submission	RG-046–053	No false success after timeout or uncertain result
UI-FR-05: Financial formatting	Normal inquiry and exact-value fixture tests	Correct money, date, direction and account masking
UI-FR-06: Authorization	RG-034–045, RG-071–078	No unauthorized fields rendered
UI-FR-07: Human handoff	RG-098–100	Verified receiving-team entitlement and delivery state
UI-FR-08: Data protection	RG-093–097	No protected data leakage through UI or context
UI-FR-09: Adversarial resilience	RG-054–060	Prompt injections cannot change permissions or presentation rules
UI-FR-10: Session recovery	RG-061–070	Sensitive content hidden on expiration or revocation

These are proposed mappings; some requirements (particularly precise amount formatting, accessibility, and every visual transition) need dedicated UI-level test cases in addition to the existing 100-case agent evaluation dataset.
8. Recommended MVP screen priorities
Priority	Screen or component	MVP decision
P0	Support home and service quick actions	Build
P0	Conversational message feed	Build
P0	Secure sign-in/step-up handoff	Build
P0	Authorized transaction card	Build
P0	Fraud/error intake and submission states	Build
P0	Case status card and tracking	Build
P0	Human-support handoff and failure states	Build
P0	Session expiration, privacy and masked data	Build
P1	Conversation history across sessions	After privacy and authorization review
P1	Rich attachment uploads	Controlled extension
P2	Investments, loans, fixed deposits, merchant servicing	Out of current MVP
P2	Customer-facing voice assistant	Separate channel evaluation

9. Product recommendation
The reference screenshots demonstrate a useful menu-driven support experience, but ResolveGuard should improve it through context-aware conversations with explicit, backend-verified workflow states.

I recommend three core UX rules:
1. Never request or reveal unnecessary sensitive information. Authentication belongs in the trusted banking interface, not in conversational text fields.
2. Never confuse an attempted action with a completed action. Report capture, case creation, case resolution, and handoff confirmation need distinct visible statuses.
3. Never show financial facts without permission and provenance. Amounts, merchants, dates, case IDs, and policies must come from authorized systems and approved sources.
These specifications are intended for product and engineering design review. They do not constitute approval of the final masking standards, authentication policies, or regulatory messaging, which remain institution-owned decisions.

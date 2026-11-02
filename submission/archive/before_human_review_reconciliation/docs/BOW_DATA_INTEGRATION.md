# Bank of Whatever workbook integration

Implemented October 30, 2026 (America/Los_Angeles). Synthetic demonstration only.

Execution update: a separate local BOW runner now executes all 100 imported
scenarios and records results under `artifacts/local_completion/bow100_final_checked/`.
Original workbook execution-status cells remain unchanged as source provenance.
Local behavior checks pass; sixteen required/forbidden tool conflicts and human
reference qualification remain flagged. See [local completion](LOCAL_COMPLETION_REPORT.md).

Conversation update: public answers are now specific to the question (fee amount, waiver conditions, APY, rewards or eligibility). Missing or incompatible product context produces product buttons inside the chat. A typed product name or ordinal resumes the saved public question; the sidebar follows the resolved selection. Explicit product names in a question override a stale sidebar value without combining policies. Browser-bound public context survives application restarts and is cleared by a new conversation or knowledge-source change. Same-key retries are stable; cached public answers are not reused across source-version or date changes. Public clarification never grants private account access.

Strict product verification update: a sidebar value alone is a hint, not a confirmed product. Policy terms require an explicit product in the question or a previously confirmed in-chat product. A category-only reply such as "Checking account" preserves the original question and asks for Everyday, Plus or Premier before quoting terms. The separately selectable original demo now follows the same clarify-first sequence with its own products and evidence. Public context is bank-separated, and responses cached before this logic version are not reused.

Fee features are also checked: monthly maintenance rules are not substituted for an ATM, overdraft or annual-card-fee question. When the source lacks that specific charge or waiver, the response identifies the missing policy rather than inventing a figure. The example pairing a $12 checking fee with a $1,500 waiver balance is not adopted as BOW policy: those values belong to different BOW tiers. Personal waiver eligibility remains unconfirmed without the verified account facts required by the applicable rule; customers are not asked to type private financial details into chat. Sign-in permissions and immediate fraud/error intake remain separate from public product clarification.

## Authoritative demo source

The first named file, `ResolveGuard_PM_Consolidated_Review_Pack.xlsx`, contains the archived ResolveGuard baseline and no BOW sheets. Following the user's clarification to use the attached file, the newer `Bank_of_Whatever_ResolveGuard_Synthetic_Review_Workbook.xlsx` was located and inspected. It contains all 11 required BOW worksheets. It is the active BOW source.

Source SHA-256: `13ffcfdc9eb020e8bcd8e0908445eeda6384aba71d0da02ef9f5433686a48ff8`.

The exact workbook is copied into `data/bow/<source_sha256>/source.xlsx`. Normalised JSON files, row-level worksheet lineage and field-file fingerprints are stored beside it. `data/bow/active.json` selects the validated snapshot. Neither workbook in Downloads was modified.

| Worksheet | Imported records |
| --- | ---: |
| BOW Products | 11 |
| BOW Policies | 19 |
| BOW RAG Chunks | 61 |
| BOW Customers | 12 |
| BOW Accounts | 12 |
| BOW Transactions | 48 |
| BOW Sessions | 12 |
| BOW Cases | 12 |
| BOW Delegations | 2 |
| BOW Intake Events | 1 |
| BOW Eval Golden | 100 |

Archived worksheets remain in the exact source copy but are not merged into the BOW runtime. The earlier six-product chat-table draft is superseded and inactive; it is not a replacement for the workbook.

## Import validation

`tools/import_bow_workbook.py` reads XLSX ZIP/XML with the standard library. It treats workbook text as data, not agent instructions; it does not follow links or execute macros/formulas. Formula cells in imported BOW tables are rejected. Missing sheets, incorrect counts, malformed fields, duplicate/wrong-bank identifiers, unknown product/account/customer relationships, mismatched policy/chunk scope and changed chunk text hashes fail validation before activation.

Pydantic models preserve source values, including customer KYC REVIEW labels, negative transaction cents, revoked/unauthenticated sessions and PENDING_REVIEW cases. Excel serial timestamps and date-only expiry values are interpreted as UTC for this synthetic demo. That assumption is explicit in the manifest; original bytes are preserved.

The seeded intake event remains source reference data. Importing it does not create a new durable report, determine legal receipt, or initiate an investigation.

## Public products and policy retrieval

BOW is the default UI knowledge source. The original ResolveGuard baseline remains explicitly selectable and separate. Guests select an exact BOW product before product-specific answers; a generic savings-rate question asks which product rather than guessing. The source workbook now provides fee effective dates, expiry dates and High-Five tier thresholds, replacing the gaps in the initial chat-table draft.

- Everyday Checking: $6 monthly; the supplied direct-deposit/balance waiver remains tied to Everyday.
- Plus Checking: $12 monthly; its own $2,000 deposit / $10,000 combined-balance conditions apply.
- Premier Checking: $25 monthly; its own $25,000 combined-balance condition applies.
- Starter Savings: illustrative 2.00% variable APY.
- High-Five Savings: illustrative 3.20% below $10,000; 3.50% at $10,000 or more.
- Premier Savings: illustrative 3.65%; Premier Checking relationship conditions apply.

These are invented BOW terms, not real banking offers. The workbook's effective date is October 1, 2026 and policy expiry is December 31, 2026. For fail-closed retrieval, `expires_on` is treated as an exclusive boundary: the snapshot is unavailable on and after that date. This convention should be confirmed before production use.

The 61 source chunks are preserved as supplied, not silently regenerated. A chunk must agree with its parent policy's bank, product, access, approval, dates, topic and refresh rule; its text must occur in the parent and match its supplied SHA-256. The short source chunks include fee/waiver rule blocks and separate APY/reward fragments. Answer composition uses the applicable parent/product context so conditions are not lost when a rate or reward appears in another fragment.

Retrieval enforces bank BOW, exact product or explicitly applicable group (`ALL`, `ALL_SAVINGS`, `CHECKING_DEBIT`), PUBLIC access, source test approval and validity dates before ranking. Exact product evidence ranks ahead of general operating guidance. Production retrieval without explicit demo permission does not accept the fictional approval tag. No Chase, Capital One or archived ResolveGuard policy is a fallback.

Sources show original chunk IDs, parent policy IDs, product IDs, text hashes, source workbook, version, effective date and expiry. Structured fee amounts also cite BOW Products; they are not inferred from unrelated policy wording. Credit-card product information is public, but credit-card servicing remains outside the MVP.

## Protected data and guest-first behaviour

The web session is bound to its backend bank. An original-demo sign-in is not a BOW identity. A saved BOW request must resume through BOW sign-in, with current ownership and tool permissions checked again.

`BowBackend` loads only the BOW customers/accounts/transactions/cases/sessions/delegations. It uses the existing deterministic tool boundaries and durable support/report storage. Wrong-bank requests are denied in the backend itself. Public policy choice cannot override the product relationship of an authorised account or payment: protected fee explanations derive their product from the actual permitted account.

The UI offers BOW Customer 01 and 02, plus an additional-verification example for BOW Customer 03. All 12 source sessions remain available as imported fixtures for validation. Revoked and unauthenticated examples remain blocked. Demo risk rule: an active AAL1 source session needs the separate simulated check before protected reads; this is a declared demo rule, not a real bank risk policy.

Masked account labels come from authorised BOW account data. Signed transaction amounts are preserved exactly. No balances or direct-deposit eligibility measurements are invented; the assistant cannot establish that a customer qualifies for a waiver from the current fields.

Fraud/error intake is preserved before authentication, with BOW bank context stored in the report payload. Report capture, formal-notice review, verification, investigation and support delivery remain independent. Case creation still requires explicit draft confirmation. No real bank connection or money-changing tools were added.

## Evaluation status and review exports

All 100 BOW scenarios retain source `NOT_RUN` status and source provenance. Their expected bank/product, intent, authentication behaviour, allowed/forbidden tools, safety flags, outcome and risk level are preserved. The worksheet name "Golden" does not establish human approval or prove evaluation execution. No expected values are passed to the model or used as runtime routing rules.

Application regression tests and browser checks cover bank/product isolation, product fee/APY presentation, source dates, private ownership, original-request resumption, additional verification and reporting. These tests are not a claimed scored execution of the 100 new scenarios. A dedicated BOW scenario runner/review remains a next step.

Build the local readable review pack with `python tools/build_bow_review.py`; open `artifacts/bow_review/index.html`. The ZIP contains exact source workbook, JSON/CSV records, the source manifest and row lineage. Browser sign-in bindings, credentials and live customer records are not part of this source-data review package.

## Implementation references

- `resolveguard/bow_data.py`: strict schemas and source integrity checks.
- `resolveguard/bow_knowledge.py`: metadata-filtered retrieval and public answers.
- `resolveguard/bow_backend.py`: isolated BOW fixture backend and account-bound policy context.
- `resolveguard/web.py`: guest-first bank context, sign-in and resumption.
- `tests/test_bow.py`: source, filter and authorisation regression tests.
- `artifacts/bow_workbook_inspection_latest.json`: corrected workbook coverage inspection.

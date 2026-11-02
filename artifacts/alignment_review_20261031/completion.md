# ResolveGuard local implementation completion

Completed local implementation and verification after the October 31 review.
Scope excludes LangSmith Cloud, Replit deployment and real bank integrations.
This is a synthetic learning/demo application. Human reference approval and
production qualification are separate from implementation completion.

## What changed and why

| Step | What now works | Why it matters | Verification |
| --- | --- | --- | --- |
| 1. Check answer claims | Controlled public answers are reconstructed and compared; financial amounts and conditions are checked. Private payment descriptions are compared with authorized records. Catalog facts now have explicit evidence. | A real citation cannot make an incorrect fee or condition true. | Changed-fee and reversed-condition tests; the original RG-056 retrieval failure is fixed. |
| 2. Make session reviews useful | Unmeasured intent accuracy remains visible without automatically escalating every clean session. Failed checks and privacy signals still require review. | Reviewers can distinguish missing measurement from a confirmed problem. | Clean, failed and incomplete-session tests. |
| 3. Review the whole journey | Independent local checks examine delivered replies, receipt ownership, report preservation and duplicate commits. | An individually safe reply does not establish that the whole journey was handled correctly. | Session trajectory checks, restart recovery and failed-turn tests. |
| 4. Preserve audit history | Requests retain their original conversation generation after reset. New evidence creates another audit revision; previous reports are retained. | A late result must not rewrite history or appear in a new conversation. | Reset-during-request and late-evidence revision tests. |
| 5. Execute full local suites | Separate runners execute the original 100 and BOW 100 scenarios with isolated state, saved results and actual traces. | Imported cases are not test results. | Both suites pass their implemented local behavioral assertions; qualification remains pending. |
| 6. Add the reviewer workspace | Staff can search sessions, inspect recorded steps, sources, access decisions, delivered text and audits, and append review notes. | Failures become explainable and actionable. | API scope/privacy tests and ten read-only browser checks. |
| 7. Protect reviews and exports | Bank-scoped VIEWER/REVIEWER/ADMIN roles, one-hour created tokens, revocation, logout clearing, concurrent-edit protection and encrypted exports. | Review access must not grant banking powers or expose unprotected evidence. | Cross-scope denial, revision conflict, encryption/decryption, tamper and revocation tests. |
| 8. Add operational coverage | Local API and workflow observations include public and private paths. Configurable rules flag denied access, failed checks, confusion, latency and review backlog. | Operators need visibility even when a failure is handled safely. | Dashboard/API tests, operations browser checks and local alert acknowledgement tests. |
| 9. Expand model evaluation | Twelve public-policy questions have actual RAGAS metrics and LLM-judge grades. Twelve balanced calibration examples have actual model grades, with development/holdout tags. | Model opinions need broader evidence and human comparison. | Twelve valid semantic results and twelve valid calibration grades, retained separately from mock banking tests. |
| 10. Add human reference review | A person can approve/reject proposed expected answers with a source hash, identity, note and explicit attestation. Judge/human agreement stays unavailable until human labels exist. | AI-authored examples cannot certify their own correctness. | Source-change rejection, missing-attestation and disagreement tests. |
| 11. Add demo operational commitments | Versioned local rules assign priority from verified support receipts. A signed-in customer may explicitly request a simulated callback for an owned, acknowledged handoff. | Priority and callback claims need backend records, not model promises. | Retry, ownership, consent, queue-outage and revoked-delegation tests. |

These steps were implemented incrementally, with targeted checks after each
change and broader regression checks after integration. The original workbooks,
product PDFs and bank fixture files remain unchanged. Three additional fee events
and one paper-statement policy exist only as declared, draft evaluation fixtures;
they are not silently activated as bank terms in customer chat.

## Customer privacy and consent

Family relationships do not grant access. Spouses, parents, children, friends and
other third parties must pass backend identity and resource/action permission
checks. A message saying that the customer consented is not evidence of consent.
Only a trusted backend authorization record can establish access.

Tests cover guest family claims, an authenticated spouse attempting another
customer's case, valid narrow power-of-attorney access, denied transaction access
outside that authority, and revocation. Callback confirmation rechecks current
case authority; an old handoff receipt does not preserve revoked access rights.

Reading an existing case and creating a case are separate permissions. A
representative with read-only case access cannot create a case. The backend also
requires a service explicitly permitted to write cases; read authority alone is
insufficient. Authentication continuation links preserve the session timeline
without transferring account permissions.

For RG-040, the original question is about a case while the source label says
transaction inquiry. The versioned bindings normalize it to a case inquiry and
require verification before disclosure, based on the user's privacy clarification.
The original source label remains in `source_contract`; general dataset approval
is still pending. Earlier attack-route changes are also explicit versioned
translations rather than edits to the workbook.

## How the app works now

The customer still speaks to one assistant. Security checks run first. Public
questions identify the product and retrieve its current fictional terms. Personal
requests require demo sign-in and backend authorization. Possible fraud/error
reports are preserved before private lookup. Draft case creation requires explicit
confirmation and stable retry keys.

Resolution records supported next steps and local queue ownership. The reply
checker checks the final answer, records and sources before delivery. Session-end
work is durable and runs separately from sending messages. The reviewer workspace
plays recorded evidence; it never repeats a banking action.

The web app still uses controlled templates and a mock router. Actual Nebius
models evaluate synthetic public answers separately. This work does not enable
unrestricted generated replies or send live customer conversations to a provider.
LangGraph orchestrates account conversations; direct public web paths now also
record retrieval and source-date checks. Pydantic validates external data shapes.

## Results and review items

| Evidence | Result and limits |
| --- | --- |
| Python regression checks | 272 main tests: 271 pass and one expected dependency-branch skip. All 13 synthetic-fixture tests pass. |
| Original suite | 100/100 local checks pass; proposed fixture bindings and versioned expectation translations remain subject to human review. |
| BOW suite | 100/100 local behavior/tool-path checks pass. Sixteen source rows list a tool as both required and forbidden; those contradictions block qualification rather than disappearing from the report. |
| Adversarial suite | 8/8 pass, including no sign-in continuation for explicit attacks and preserved fraud intake. |
| Customer browser checks | 48 pass. Checks of answer focus use visible text, not hidden content inside the collapsed evidence panel. |
| Operations browser checks | 7 pass, including trends, trace history and mobile layout. |
| Reviewer browser checks | 10 pass, including access denial, evidence display, draft datasets, human-attestation defaults and protection against late responses after logout. |
| Expanded semantic suite | All 12 cases have metrics and valid judge grades; the judge passes 12/12. RAGAS faithfulness remains 0.5 on SEM-003 and SEM-011 and is flagged for human assessment. Other valid low scores are not replaced by retries. |
| Judge calibration | Twelve actual grades are recorded. They match the proposed examples, but human-model agreement is still unscored because independent human labels have not been supplied. |

The first expanded semantic run exposed missing catalog evidence and two truncated
judge outputs. It is preserved in `semantic_expanded_01.json`. The second run is
also preserved. One draft reference incorrectly bound Debit Plus to Debit; a new
validation guard rejects that mismatch. Only that corrected case was remeasured.
The consolidated final report verifies identical model inputs before retaining the
other eleven measurements. Changes in references/evidence are not represented as
an isolated improvement in model quality.

The two remaining faithfulness flags concern the phrase "demo terms": the NLI
verifier rejected it despite fictional/test provenance. Its statements and reasons
remain visible for human review. The application does not convert those opinions
into permission or a banking commitment.

## Open the application

- Customer chat: `http://127.0.0.1:8765`
- Operations: `http://127.0.0.1:8766`
- Agent Review Admin: `http://127.0.0.1:8766/reviewer`

The reviewer uses the existing `RESOLVEGUARD_DASHBOARD_TOKEN` from the local `.env`.
Do not paste it into chat. Local administrators can create narrower viewer/reviewer
tokens in the workspace; those tokens expire after one hour and can be revoked.
The configured bootstrap administrator token is rotated through local configuration.
It is demo authentication, not institution staff identity.

To try a callback: sign in explicitly as a sample customer, submit an eligible
report or request support, then choose **Request a demo callback**. The app records
a simulated window and states that **no real telephone call is scheduled**.
No phone number or authentication secret is collected in chat.

## Repeat the checks

From the project directory, use the existing single Python 3.12 `.venv`:

```powershell
uv sync --extra evals
uv run --extra evals python -m unittest discover -s tests -q
uv run --extra evals python -m unittest discover -s resolveguard_synthetic_v04/tests -q
uv run --extra evals python -m resolveguard.full_evaluation --suite original --output artifacts/my-original-run
uv run --extra evals python -m resolveguard.full_evaluation --suite bow --output artifacts/my-bow-run
uv run --extra evals python -m resolveguard evaluate-security --output artifacts/my-security-run.json
```

Use new output directories so previous results remain intact. Model evaluation is
explicit, paid and separate from these local commands:

```powershell
uv run --extra evals python -m resolveguard semantic-eval --dataset data/semantic_cases_expanded_v3.json --ragas --judge --output artifacts/my-semantic-run.json
uv run --extra evals python -m resolveguard.calibration_eval --output artifacts/my-calibration-run.json
```

Only synthetic public questions, answers, reference passages and evaluation
instructions leave the machine for these commands. Customer fixture tables,
session bindings and credentials are excluded from prompts. The model key is used
only for authenticated API access. Cloud trace publishing remains off.

Decrypt a downloaded reviewer package locally; the password is requested privately:

```powershell
uv run python -m resolveguard.review_export --input review.rgexport --output review.json
```

Use an appropriate output extension for JSON or CSV. Exports use authenticated
AES-GCM encryption with a password-derived key; the password is never bundled into
the package. Protect the decrypted file. SQLite review history has application
append-only controls and integrity checks, not a production tamper-proof archive.

## What still requires a person

Review the expected answers and proposed fixture bindings, resolve the 16 BOW tool
contract conflicts, and assess the two RAGAS disagreements. Approve or reject
calibration labels before interpreting human-model agreement. Prompt authorship
provenance remains unverified; reviewing a prompt does not prove who authored it.

These are approval/evidence decisions, not unfinished buttons or hidden automatic
approvals. The workbench now supports them. Full qualification remains blocked
until its required evidence is complete. Production identity, legal decisions,
retention, independent archival protection and real service commitments are not
claimed by the synthetic implementation.

LangSmith Cloud, Replit deployment and real bank integrations were deliberately
left out, as requested. Voice, autonomous financial actions and credit-card
servicing remain outside the agreed MVP. Missing BOW payment-status definitions
still produce an honest source-gap response rather than borrowing another bank's
policy.

## Evidence locations

- `artifacts/local_completion/original100_release_check/`: results, proposed
  bindings, summary and actual traces from the original workbook.
- `artifacts/local_completion/bow100_release_check/`: BOW results, tool paths,
  source conflicts, version fingerprints and traces.
- `artifacts/local_completion/security_final.json`.
- `artifacts/local_completion/semantic_expanded_final.json`: consolidated actual
  metrics with measurement-source references and explicit low-score flags.
- `artifacts/local_completion/judge_calibration.json`: measured model opinions.
- `artifacts/customer_ui_validation/browser_checks.json`.
- `artifacts/observability_browser_checks.json`.
- `artifacts/local_completion/reviewer_browser_checks.json`.
- `artifacts/web.sqlite3`: local banking events and staff-protected review evidence.
- `artifacts/operations.sqlite3`: minimized local observations.

The original requirements are in the unchanged PRD/BRD PDFs. The earlier
[alignment review](IMPLEMENTATION_ALIGNMENT_REVIEW.md) is retained as the
pre-implementation snapshot; this report is the current completion record.

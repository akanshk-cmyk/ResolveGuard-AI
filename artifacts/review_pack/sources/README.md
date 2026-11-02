# ResolveGuard credential-free implementation

ResolveGuard is a synthetic U.S. checking/debit support demonstration. This implementation provides durable intake, scoped fixture reads, local policy RAG, a mocked conversational model, a LangGraph graph definition, local execution traces, and a 40-case evaluation runner. It does not call Nebius or use real customer records.

## Current execution status

- The runnable default is the explicitly labeled **offline executor**. It runs the same node functions and branch decision used by the LangGraph definition.
- `--engine langgraph` compiles a real `StateGraph`. LangGraph 1.2.19 and LangSmith 0.14.16 are now installed in `.venv`; graph execution is locally verified across all 40 cases with three repeats. Graph/offline parity tests pass.
- LangSmith dataset upload, nested trace publishing, and SDK evaluation adapters are prepared. Real SDK `RunTree` construction is tested with create/update operations intercepted locally. No hosted traces or experiments have been created; live Cloud authentication, uploads and experiments remain unverified.
- `MockModel` uses ordinary text rules and a fixed evidence-backed response. It never receives expected labels, case IDs, or fixture fault controls. Its errors are diagnostic, not GLM-5.3-Flash benchmark results.
- Pydantic v2 now validates request/routing boundaries, backend and policy results, and durable event payloads. Both engines have been rerun after migration; quality assertions match the prior mock evidence.
- The 40 selected prompts are unchanged from the supplied workbook. Labels and AI-authored fixture bindings are **drafts pending human review**. Original prompt authorship is unknown: the assignment's less-than-20% LLM-generation rule cannot yet be attested.
- Original PDFs, workbook, and synthetic tool files are unchanged. Supplemental policies and records are explicitly invented fixtures.
- The three reviewed continuity gaps are fixed: created cases are readable from durable storage, step-up assurance covers restricted reads/writes, and unsupported-action wording does not hide report/handoff outcomes.
- `ConversationService` now uses actual SQLite LangGraph checkpoints, session/browser-bound threads, crash recovery and saved expiring drafts. Confirm/cancel actions bind to the stored draft; revoked permissions are rechecked, including cached responses.
- A local FastAPI customer interface is implemented, with synthetic profiles, scoped transaction selection, report and handoff cards, source references, confirm/cancel controls and session restoration. See [LOCAL_DEMO.md](LOCAL_DEMO.md). Replit configuration is prepared; no app was deployed.
- A disabled-by-default Nebius adapter is implemented and tested with fake HTTP responses. `--provider nebius` explicitly enables paid calls after key setup; none have been made. Web mode remains mock-only and never uploads to LangSmith.

## Run locally without credentials

Run commands from this repository root with the installed project virtual environment. Both execution engines now require Pydantic; the sequential executor does not require LangGraph or LangSmith.

```powershell
.\.venv\Scripts\python.exe -m resolveguard ask "I did not authorize this debit and want a human" --transaction TXN-001-01 --request-key demo-001 --db artifacts/demo.sqlite3
.\.venv\Scripts\python.exe -m resolveguard ask "Show the selected transaction" --transaction TXN-001-01 --request-key inquiry-001
.\.venv\Scripts\python.exe -m resolveguard index --output artifacts/policy_chunks.json
.\.venv\Scripts\python.exe -m resolveguard evaluate --engine langgraph --output artifacts/my_mock_run --repeat 3
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m unittest discover -s resolveguard_synthetic_v04/tests -v
```

Evaluation output directories must be new. Databases are isolated by case and repeat; the same-request retry case makes two calls against one database. For `ask`, reuse the database and request key to test persistence across process restarts. Changing the report's text or selected transactions with the same key returns a conflict instead of overwriting the original. New reports need new keys.

`--strict` returns a nonzero exit code for mock/draft runs because they cannot qualify a release. Normal evaluation returns zero when diagnostic execution completes, even if cases fail. `--require-reviewed` rejects datasets whose human approval and provenance are incomplete.

## Review the dataset

`data/evaluation_40.json` contains 20 happy paths, 12 edge cases, 6 anticipated failures, and 2 adversarial cases. Scenario type is a teaching selection tag; severity is preserved separately. The wider 100-case suite is not replaced or claimed executed.

Open `data/review_40.csv`. Review the source prompt/behavior, complete expected assertions, fixture bindings, and injected faults. Record `APPROVED` or `REJECTED`, your reviewer name, and review notes. Leave cases pending when ambiguous. Resolve actual prompt provenance with evidence; do not mark an AI-generated prompt human-authored merely because a person reviewed it.

```powershell
python tools/apply_review.py --output data/evaluation_40_reviewed_v2.json
python -m resolveguard evaluate --dataset data/evaluation_40_reviewed_v2.json --require-reviewed --output artifacts/reviewed_mock_run
```

Import creates a new version and does not overwrite the original. Changing expected truth requires a reviewed annotation. If the oracle changes, run both comparison versions against the corrected frozen dataset. Regeneration via `python tools/prepare_dataset.py` uses the supplied workbook and refuses to overwrite existing reviewer annotations.

## Data flow and controls

### Pydantic validation boundaries

`Request`, `Route`, and fault controls now use strict Pydantic v2 models. Requests and routes are immutable; simulator controls validate assignments. Unknown fields, string/numeric booleans, missing routing flags, invalid selectors and duplicate selected transactions are rejected. JSON arrays are explicitly normalized to tuples without coercing individual values. Original report whitespace is preserved.

Backend reads, report/case outcomes, handoffs and retrieved policy passages have separate schemas. Success requires the corresponding record or commit fields; denied/unknown reads cannot carry records, and failed handoffs cannot carry context. Amounts must be integer cents, dates must be real ISO dates, and event timestamps must have timezones. Output dictionaries remain compatible with the existing evaluator, but are validated before they enter workflow state.

SQLite validates payloads and complete success records before writing and revalidates persisted records on lookup/replay. Tool validation failures become safe UNKNOWN outcomes with error codes; rejected values are not logged. Model routing failures retain the existing explicit-report fallback. The CLI prints only validation field paths and error codes, never rejected values.

`WorkflowState` intentionally remains a mutable internal dataclass: Pydantic validates external boundaries rather than pretending each state snapshot proves an outcome. Authorization and exact backend event checks remain independent. Conversation checkpoints are owned by the separate `ConversationService`; the request-scoped inner graph explicitly disables checkpoint inheritance.

Export schemas with `.\.venv\Scripts\python.exe tools/export_contracts.py`; see `artifacts/pydantic_contracts.json` for the machine-readable contracts.

1. Validate caller-supplied synthetic session and resource selectors with Pydantic. These simulate a trusted application session; they are not production authentication or signed identity tokens.
2. A mock classification returns a primary intent plus independent fraud and human flags.
3. If a potential error is detected, preserve the original text and timestamp in SQLite **before** restricted record reads. Model/schema failure has a limited explicit-fraud fallback; this is not comprehensive fraud detection.
4. Recheck service, principal, account and delegation permissions on backend reads. A separate simulated assurance event is required for the step-up fixture. Case writes require explicit confirmation.
5. Retrieve current, approved, product/jurisdiction-matching policy passages from a local keyword index. Overlapping active policy versions fail closed. Obvious injected policy instructions are filtered, but the filter is not a comprehensive prompt-injection defense.
6. Simulate queue availability and receiving-field entitlements. Acknowledgment, unknown delivery and unavailability are distinct. Primary urgent-queue outages use a seeded backup; both queues down retain the report without claiming a connection.
7. Assemble only authorized records and selected passages for explanation. The response must match a deterministic evidence-backed template; altered model output is replaced. The first Nebius adapter is classification-only and keeps this template protection. This is not a general semantic verifier for future free-form live answers.
8. Persist privacy-minimized local traces with nested node, mock-model and tool spans. No code auto-publishes traces; graph auto-tracing is suppressed even if ambient environment settings enable it.

Report capture, legal notice review, identity verification, investigation, customer acknowledgment and handoff are separate states. No statutory deadlines are calculated. No refunds, transfers, credential changes, card freeze or dispute adjudication tools exist.

### Policy chunking

Short existing documents remain intact. Paragraph/heading blocks are preserved; long ordinary prose splits at sentence boundaries, with a target of approximately 400 whitespace tokens and 50-token overlap. Tables, numbered procedures and rule/exception paragraphs are kept whole and flagged if oversized. This tokenizer is an approximation, **not** GLM's billing tokenizer. Passages keep source IDs, section/title, version, product, jurisdiction, approval and dates. No embeddings or vector database are required for the initial keyword index.

### Storage boundaries

SQLite enforces one `(kind, owner, request_key)` event with a payload hash in a transaction. Reports, cases and handoffs have separate event namespaces. Reconciliation distinguishes pre-commit outage from lost post-commit responses. Raw synthetic narratives stay in the local report database; model contexts, traces and handoff payloads do not contain them. This is demo persistence, not encrypted production recordkeeping. Anonymous callers must receive distinct trusted session bindings in a real app; the supplied `SESS-ANON` is one synthetic test identity.

## Results and evaluators

Pydantic migration evidence remains in `artifacts/pydantic_langgraph_verified/` and `artifacts/pydantic_offline_verified/`. Current incremental verification is in `artifacts/implementation_increment_report.json`, with controlled mock experiments in `artifacts/mock_iterations_final/comparison.json`. On the unchanged 40-case draft development set, routing moved from 85% to 100%, complete-case success from 80% to 97.5%, and fraud recall from 80% to 100%. Each version ran three times; no measured case-pass regressions occurred. RG-056 remains a policy-retrieval failure. These are mock-rule results, not GLM scores or independent qualification evidence. Human review remains pending. Mock experiments blocked outbound sockets.

Each evaluation writes:

- `summary.json`: dataset/code/fixture fingerprints, aggregate mock metrics and explicit release blockers.
- `scored_results.csv`: per-case routing, PASS/FAIL, failure labels and trace IDs.
- `results.json`: expected assertions, actual outcomes and all attempt evidence.
- `traces.jsonl`: sanitized nested spans, including every retry attempt.
- `failure_analysis.json`: failed assertion clusters, example IDs and illustrative rework estimates. These are symptoms requiring human root-cause review, not automatically proven causes.
- `isolated-state/`: SQLite records for reproducing persistence and reviewing original synthetic text locally.

Deterministic checks compare record fields with independent fixture references, captured originals with SQLite, case creation with commit events, handoffs with acknowledgment records, and policy citations with explicit gold source requirements. Tests include tampering, wrong-owner access, concurrent retries, timeout recovery, receiver scope, malformed model output and secret redaction.

Local mock latency is not provider latency. Mock token usage is unknown/null and provider cost is zero because there are no provider calls. If the operator explicitly selects Nebius, the adapter reports actual returned token usage and an estimated list-rate cost; missing usage stays unknown. Human semantic review and a real GLM baseline remain outstanding. A mock diagnostic pass never grants demo/pilot release approval.

Four controlled mock iterations are available through `tools/compare_mock.py`, preserving the original 40-case dataset and exporting observed failures as regression cases. These changes do not establish real GLM improvement or independent holdout performance.

## Installed dependencies and optional LangSmith Cloud setup

Dependencies are installed in `.venv`. Reproduce the verified package versions using `requirements.lock.txt`; `requirements.txt` retains the broad compatible ranges. The lock snapshot was produced on Windows with Python 3.14.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m resolveguard evaluate --engine langgraph --output artifacts/langgraph_mock_run
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

`.env.example` documents optional variables; commands read process environment variables and do not implicitly load `.env`. Keep real keys out of source, review files and outputs.

Only after explicitly configuring LangSmith credentials, the following command performs network writes:

```powershell
python -m resolveguard publish --dataset data/evaluation_40.json --traces artifacts/my_mock_run/traces.jsonl
```

It uploads a new versioned **draft** dataset plus sanitized mock traces. Publishing alone does not create a scored experiment. The prepared `evaluate_in_langsmith(dataset_name, dataset, engine="langgraph")` adapter runs scored SDK experiments and attaches nested local spans to each SDK run; actual Cloud evaluation remains unverified and requires a separate explicit action. Mock fault bindings are resolved from the matching frozen local case and are never given to the conversational model.

Implementation references: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [LangSmith evaluation](https://docs.langchain.com/langsmith/evaluate-llm-application), [trace data masking](https://docs.langchain.com/langsmith/mask-inputs-outputs).

# ResolveGuard evaluation and operations runbook

## Verification status

Current local completion is documented in [LOCAL_COMPLETION_REPORT.md](LOCAL_COMPLETION_REPORT.md).
The customer app now records minimized API and workflow observations by default
in `artifacts/operations.sqlite3`. The reviewer workspace at
`http://127.0.0.1:8766/reviewer` adds scoped local staff access, recorded session
evidence, reviews, audit revisions, encrypted exports, label/calibration review
and configurable local alerts. Cloud verification and deployment remain excluded.

The expanded semantic source is `data/semantic_cases_expanded_v3.json`.
`artifacts/local_completion/semantic_expanded_final.json` contains 12 measured
cases with all judge grades valid, including two retained low faithfulness scores.
`judge_calibration.json` holds 12 actual model opinions. Human calibration is
pending. Judge output allowance is now 8,192 tokens after observed truncations;
the earlier pilot descriptions below remain historical evidence.

The deterministic application runner remains local by default. Semantic evaluation and cloud verification are explicit commands. Implemented adapters are not evidence of successful hosted runs. Check `cloud_verification.json` for `VERIFIED` and `semantic_results.json` for `COMPLETE`; errors and absent credentials never produce passing scores.

RAGAS/OpenAI/Instructor dependencies are declared in the `evals` extra of `pyproject.toml` and resolved in `uv.lock`. The project now selects Python 3.12.15: the Python 3.14 Windows installation attempted to compile `scikit-network` and failed because Microsoft C++ Build Tools were absent. Python 3.12 has a published prebuilt wheel. The older requirements files remain historical/compatibility inputs.

## Configuration

From `.`, open `.env` in your editor. `.env.example` is the template, and `.env` is excluded by `.gitignore`. Do not send keys in chat or commit them. Evaluation and dashboard CLI commands explicitly read this file; the customer web server does not implicitly load it.

```dotenv
LANGSMITH_API_KEY=your-key
LANGSMITH_PROJECT=resolveguard-demo-eval
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING=false
RESOLVEGUARD_CLOUD_TRACING=false
NEBIUS_API_KEY=your-key
RESOLVEGUARD_JUDGE_MODEL=zai-org/GLM-5.3-Flash
RESOLVEGUARD_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
RESOLVEGUARD_MONITOR_DB=artifacts/operations.sqlite3
RESOLVEGUARD_DASHBOARD_TOKEN=choose-a-random-secret-at-least-24-characters
```

Existing process settings take precedence. Normal customer chat remains mock-based. The verification command explicitly enables tracing only around its experiment; it does not require turning runtime export on.

## Install optional semantic dependencies

```powershell
uv sync --extra evals
uv pip check
```

These commands download packages from the configured package registry and sync this project's `.venv` using `uv.lock`. They do not publish banking data. Use `uv run --extra evals python ...` for semantic commands so the selected extra remains explicit. The original `requirements-evals.txt` remains a compatibility declaration; `pyproject.toml` and `uv.lock` now drive project dependency management.

## Cloud smoke experiment and remote verification

```powershell
.venv\Scripts\python.exe -m resolveguard verify-cloud --output artifacts/cloud-smoke-001.json --limit 3
```

This creates a new hosted dataset and runs a local mock LangGraph target tracked by a LangSmith experiment. It uploads nested execution spans and boolean evaluator checks, then reads back remote examples, root runs, nested spans and feedback. Cloud hosting applies to the experiment records, not inference execution. The smoke target is deliberately mock-based, so a successful upload does not establish GLM answer quality.

What leaves the machine for LangSmith:

- Generated `CASE-000` identifiers and a fixed placeholder message, not customer questions.
- A reference-retained-locally flag, not raw expected transaction/case records.
- Span UUIDs, allowed step names, timestamps, durations and boolean execution errors.
- Boolean deterministic checks, dataset fingerprints and mock experiment metadata.

Customer/account IDs, statements, prompts, financial records, tool payloads and final response text are omitted from cloud exports. This is structural minimization rather than a claim that regex masking can detect every possible form of PII. Local evaluation files retain the existing richer evidence and need filesystem access controls.

Verification writes a status file even on failure. A partial upload may remain hosted after failure; dataset ID is recorded when known. Use a fresh output path on retry. Remote indexing delays can cause a verification failure; inspect the recorded dataset/experiment in LangSmith before rerunning. The command does not delete remote resources.

## Formal semantic scoring

```powershell
uv run --extra evals python -m resolveguard semantic-eval --ragas --judge --output artifacts/semantic-001.json
```

This sends three **synthetic public BOW policy** questions, actual application responses and retrieved policy chunks to Nebius. It also sends independent draft reference answers for reference-based metrics and the banking rubric to the judge. Answer relevance sends generated questions to the configured Nebius embeddings model. No customer fixture tables, session bindings or credentials are placed in evaluation prompts. These are paid provider requests; no price or quality claim is inferred from mock tests. RAGAS usage analytics are disabled.

The pilot lives in `data/semantic_cases.json` and checks the active workbook snapshot hash. Its source chunk IDs are independent of retrieval results. References remain pending human approval. It is separate from both the legacy 40-case suite and the imported 100-case BOW suite.

Metrics use the RAGAS collections API:

| Metric | Inputs | Meaning |
| --- | --- | --- |
| Context recall | Question, reference, retrieved policy | Reference claims supported by retrieval |
| Context precision | Question, reference, ranked retrieved policy | Ranking-weighted relevance of retrieved context |
| Faithfulness | Question, actual answer, retrieved policy | Answer claims supported by the retrieved policy |
| Answer relevance | Question, answer, judge-generated questions, embeddings | Whether the answer addresses the question |

Context precision is not a cross-bank authorization control. The runner separately checks bank/product scope deterministically. RAGAS does not replace permission checks or human policy review. Provider errors/timeouts/non-finite values produce `ERROR` and null scores, never zero or a fabricated pass.

The qualitative judge grades tone/empathy, supplied-policy compliance and guardrail integrity. Each dimension has an integer 1–5, pass/fail and a short evidence-based explanation; >=4 passes. Overall pass requires all dimensions to pass. Pydantic rejects inconsistent grades, extra fields and malformed outputs. These opinions are not regulatory certification. Using the same model family for routing and judging can correlate errors; configure an independently reviewed judge before release decisions.

## Run alongside deterministic evaluation

```powershell
uv run --extra evals python -m resolveguard evaluate --provider mock-v4 --engine langgraph --output artifacts/observability-001 --ragas --judge --langsmith
```

This runs the original 40-case deterministic suite, then the separate three-case semantic pilot and three-case cloud smoke verification. Results share a directory but retain separate scope/status/fingerprints. Remove paid/cloud flags for a fully local run. `--strict` still blocks draft/mock release qualification; successful cloud publishing cannot override it.

## Local dashboard

```powershell
.venv\Scripts\python.exe -m resolveguard dashboard --port 8766
```

Open `http://127.0.0.1:8766` and enter the dashboard token. If no token is configured, the command generates and displays a temporary token in the local terminal. It remains in browser memory only; it is not saved to local storage or a URL. For this implementation review, the currently running dashboard token was saved in the local `.env` as `RESOLVEGUARD_DASHBOARD_TOKEN`.

The dashboard is a separate loopback-only service, with token-protected APIs and no customer-app permission changes. It reads local evaluation artifacts and optional aggregate SQLite observations. Panels include journey/intent/fraud-recall trends, failure counts, p95 durations, fingerprints, baseline comparisons and payload-free trace trees. Comparisons warn when dataset or fixture fingerprints differ. Semantic results saved beside a run appear in its details. Refresh occurs every 15 seconds.

Runtime metrics now include API observations and captured public/private workflow
completions. Chat/resume p95 is separated from health polling; workflow errors are
also exposed separately. Metrics do not infer session correctness without a
reference. Runtime and batch mock p95 remain distinct. Local storage retains the
newest 10,000 observations and the dashboard reads the newest 200. Observations
and repeated case runs are not unique customers.

For optional runtime aggregation, set `RESOLVEGUARD_MONITOR_DB` in the web server's **process environment** before starting it. For optional asynchronous cloud span export, also set both `LANGSMITH_TRACING=true` and `RESOLVEGUARD_CLOUD_TRACING=true`, plus key/project/endpoint. The export queue has one worker and 32 outstanding slots. Export failures emit fixed error codes without customer payloads; they do not change banking outcomes. Pending exports are not durable across process termination. This is a lightweight prototype, not a production delivery guarantee.

The original fixed dashboard thresholds remain available. The reviewer workspace
also supplies durable local alert rules and acknowledgement for failed checks,
denied access, latency, repeated confusion and review backlog. No Slack/Teams/email
notification is sent. Production identity and external notification delivery are
not implemented or implied by the local queue.

## Local verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Tests include privacy projections, dataset export shape, nested SDK traces without upload, missing-credential failure evidence, metric-error handling, judge JSON validation, policy provenance/product checks, dashboard authorization and alert thresholds. Mock adapter tests are explicitly not a real RAGAS score or remote verification.

API references used for implementation: [RAGAS collections metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/), [LangSmith evaluation API](https://reference.langchain.com/python/langsmith/client/Client/evaluate), [Nebius Qwen embeddings](https://nebius.com/services/token-factory/models/qwen-models-inference).

## Verified semantic pilot — October 31, 2026

Python 3.12.15 and the `evals` extra are installed in the single project `.venv`.
`langchain-community==0.4.1` is pinned because 0.4.2 removed a VertexAI import
required by RAGAS 0.4.3 (see the [upstream issue](https://github.com/vibrantlabsai/ragas/issues/2745)).
Dependency compatibility and the full application/fixture tests were checked after migration.

Evidence is in `artifacts/semantic_pilot_20261031/`:

- `run_01.json`: first measured pilot. RAGAS scores calculated; two judge outputs truncated at 1,500 tokens.
- `run_02.json`: corrected source evidence includes actual catalog product names and policy dates; judge limit increased to 4,096. All judge grades returned, but one faithfulness execution was truncated.
- `metric_recovery_01.json`: both bounded retries at 4,096 tokens failed. These failures remain recorded.
- `metric_recovery_02.json`: only the failed faithfulness metric replayed with an 8,192-token ceiling; completed successfully.
- `summary.json`, `scores.csv`, `report.html`: combined results, with recovery lineage and original failures retained. Completion means measured outputs exist; it does not mean every answer passed quality review.

The three answers were generated by existing BOW application templates. Live
GLM-5.3-Flash evaluated them; Qwen3-Embedding-8B provided embeddings. LangSmith
publishing stayed disabled. The reference labels remain pending human approval.

Context recall/precision were effectively 100% for all three cases. The banking
judge passed two of three: the monthly-fee answer omitted applicable waiver
conditions. Waiver-answer faithfulness was 57.1%, because operational capability
and privacy statements were absent from the retrieved product-policy excerpts.
This calls for reviewing evidence coverage, not automatically declaring those
statements false. No customer-facing answers were changed by this pilot.

The RAGAS wrapper now retains structured claim/verdict evidence and retries a
technical failure at most once. It never retries a valid low score. Judge
responses use a 4,096-token limit; RAGAS uses 8,192 to avoid the observed
reasoning-model truncation. These are ceilings, not forced token consumption.
Provider-reported usage includes failed attempts; billing is not reconciled.

For future partial failures, replay only ERROR metrics against the same frozen inputs:

```powershell
uv run --extra evals python -m tools.recover_semantic_metrics --source artifacts/semantic_pilot_20261031/run_02.json --output artifacts/semantic_pilot_20261031/new-recovery.json
```

Reload VS Code's window to refresh its Python/formatter processes after the
Python 3.12 migration. The old rollback environment was removed after tests passed.

## Approved answer and evidence fixes

The follow-up implementation preserves the workbook, draft references and original
pilot files. Checking-fee answers now include the applicable waiver terms. Personal
waiver guidance retrieves the current PUBLIC privacy chunks C02/C03 and cites them;
if unavailable, the related guidance is omitted. The public handler separately
records that personal eligibility was not checked and private records were not
accessed. These execution facts are not represented as bank-policy documents.

Retrieval metrics continue to receive policy excerpts only. Faithfulness also
receives the public handler's explicit execution state to assess operational
claims. Judge evidence uses an allowlist of scope and authentication/permission
booleans; credentials, identifiers and arbitrary authorization fields are excluded.
Missing/invalid boolean outcomes remain unknown, never coerced into authorization.

`run_03.json` completed all four RAGAS metrics and all three banking reviews with
no technical errors. All three judge grades passed; faithfulness was 100% on these
three public cases. Answer relevance was 94.8%, 83.7% and 88.7%, respectively.
This is a combined answer/evidence change, not an isolated model-quality comparison,
and does not validate protected-account behavior. Human reference review is pending.

The before/after report is `post_fix_report.html`; `post_fix_summary.json` preserves
the baseline and new-run hashes. The updated judge-only export is
`llm_as_judge_results_after.json`. Generate these without overwriting the baseline:

```powershell
uv run --extra evals python -m tools.compare_semantic_pilot
```

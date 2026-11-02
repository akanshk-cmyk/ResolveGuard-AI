# ResolveGuard Codebase Audit

Audit scope: application Python, static UI, tests, tools, fixture/data paths, evaluation outputs, dependency/configuration files, and documentation. This document records the original state before application refactoring. Evidence is based on AST inspection, import/reference searches, and source reads; line counts are not a complexity or quality score.

## Original structure and responsibilities

`main.py` starts `resolveguard.web:create_app` on localhost; `resolveguard/__main__.py` owns CLI entry points. The browser uses `resolveguard/static/`. `web.py` owns sessions, sign-in continuation, public state, chat, account list endpoints, and response review. `conversation.py` and `workflow.py` run LangGraph account/request graphs. `backend.py` and `bow_backend.py` independently check identity, resource/action authority, delegation, transaction and case access. `fraud_triage.py`, `intake_signals.py`, `storage.py`, `demo_operations.py`, and `resolution_contracts.py` preserve reports and simulated outcomes. `customer_review.py`, `review_flow.py`, and `session_quality.py` implement pre-send and post-session checks.

`bow_knowledge.py` and `retrieval.py` implement distinct BOW and legacy policy adapters. `contracts.py` supplies typed contracts. `evaluation.py`, `full_evaluation.py`, `semantic_evaluation.py`, `ragas_eval.py`, `judges.py`, and `calibration_eval.py` own evaluation paths. `telemetry.py`, `monitoring.py`, cloud/privacy adapters, `dashboard.py`, and `reviewer.py` provide diagnostics. Tests use unittest and FastAPI TestClient, not pytest. Configuration is locked through uv/Python 3.12.

## Findings

| ID | Finding | Original file/function evidence | Impact | Recommended change | Risk | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| REF-001 | Web composition has too many responsibilities | `web.py`: 756 lines; `create_app`, eight request models, SQL setup, public turn and account list functions | Harder to navigate and test in isolation | Extract request contracts, schema initialization, public policy service, authorized list services; retain route/import names | Medium | P1 |
| REF-002 | Repeated environment-file parsing | `eval_config.load_eval_environment`; `reply_generation.load_reply_environment` | Quote parsing and precedence can drift | Share the parser while keeping different allowlists, entry guards and explicit loading times | Low | P1 |
| REF-003 | Repeated fixed provider/model strings | `nebius.py`, `reply_generation.py`, `eval_config.py`, `judges.py`, `ragas_eval.py` | Future configuration drift | Centralize existing defaults without activating previously unused environment settings | Low | P1 |
| REF-004 | Account list business logic sits in HTTP routes | `web.py:transactions`, `cases` | Listing, authority checks and response composition coupled to HTTP closure | Extract listing services; preserve pagination, order, field names and calls to protected backend methods | Medium | P1 |
| REF-005 | Public retrieval/state/cache/trace orchestration sits inside API factory | `web.py:public_bow_turn` | More difficult to reason about state transactions and duplicate requests | Extract the complete existing body unchanged behind a compatibility wrapper | Medium | P1 |
| REF-006 | Compressed statements and broad orchestration files | `customer_review.py` 464 lines, `workflow.py` 409, `contracts.py` 366, `bow_knowledge.py` 315 | Readability debt | Focus this pass on bounded extractions; do not globally reformat safety logic | Medium | P2 |
| REF-007 | Similar fingerprint helpers have deliberately different encodings | `evaluation.fingerprint` uses ensure_ascii=False; `customer_review.fingerprint` uses default=str and ASCII JSON | Merging changes persistent IDs, trace links or idempotency semantics | Preserve both; document why they are not duplicates | High | P0 |
| REF-008 | BOW and legacy retrieval schemas/filter rules differ | `bow_knowledge.py:retrieve`, `retrieval.py:PolicyIndex.retrieve` | Naive consolidation could cross banks or alter date/version handling | Keep adapters and their public/private boundaries; document metadata mapping | High | P0 |
| REF-009 | Multiple routes use safety checks that resemble classification | `security_routing.py`, `intake_signals.py`, `model.py`, `fraud_triage.py` | Removing apparent repetition can remove independent defense layers | Preserve distinct security signals, fraud preservation and backend permission enforcement | High | P0 |
| REF-010 | No exact application function-body duplicates found by initial AST scan | 47 application modules; body dumps without locations; functions at least five lines | Does not exclude near-duplicates or small helpers | Target demonstrated repeated parser/default logic, not an invented duplication percentage | Low | P2 |
| REF-011 | Generated/runtime files coexist with required historical evidence | `artifacts/`, `submission/`, historical source copies, local databases and stdout logs | Easy to publish local state or discard needed evidence | Classify artifacts, strengthen ignore rules, preserve originals and use canonical indexes | Medium | P1 |
| REF-012 | Log patterns and editor lockfiles insufficiently excluded | Original `.gitignore` excludes keys, venv, SQLite and browser profiles but not all logs or Word lockfiles | Publication hygiene risk | Add explicit log/lock/database/cache exclusions; report scan findings without secret values | Medium | P1 |
| REF-013 | Documentation generators can produce earlier status wording | `tools/build_final_submission.py` and later reconciliation/report builders | Rerunning old packaging may reintroduce stale prose | Document canonical status/evidence and generator ordering; do not rewrite frozen evidence | Medium | P1 |
| REF-014 | No repository/CI/license baseline established | No local `.git` or `.github` at audit start; license unspecified | No automatic pull-request verification; no commit rollback | Create a local source checkpoint and CI configuration; no push or invented license | Low | P1 |
| REF-015 | Dead-code/dependency removal is not established safely | CLI dynamic imports, optional eval dependencies, callbacks, tests and browser handlers | Import-only heuristics can delete active optional paths | Retain candidate symbols/dependencies unless entry-point and behavioral evidence proves removal safe | Medium | P2 |
| REF-016 | Optional report authoring has machine-specific paths | `tools/build_final_project_report.py`: Windows font path and local handout path; Word rendering helpers | Authoring is less portable; not an application runtime failure | Keep out of startup/CI paths; parameterize in a separate documentation-tool increment | Low | P2 |

No source file is declared unused solely because it lacks a direct import. Optional RAGAS, LangSmith and evaluator paths have CLI/test references. Exact duplicates, test coverage percentage, cyclomatic complexity, live performance gains and production security are not inferred from this audit.

## Reference comparison

| Practice | Reference pattern | Existing ResolveGuard | Decision |
| --- | --- | --- | --- |
| API modularity | [FastAPI official multi-file example](https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/bigger-applications.md) separates routers and reusable dependencies | A large app-factory closure with important state-ordering dependencies | Extract services/contracts first; preserve route registration and factory signature |
| Workflow/state tests | [LangGraph repository](https://github.com/langchain-ai/langgraph) separates library responsibilities and checkpoint testing | Graph/state contracts already have extensive local tests | Preserve graph topology and checkpoint namespaces; avoid novelty-driven graph redesign |
| Tool configuration | [pytest project configuration](https://github.com/pytest-dev/pytest/blob/main/pyproject.toml) centralizes development settings | uv lockfile and unittest already work; no need to migrate runners | Keep unittest and the installed lock; use built-in checks/CI rather than adding dependencies just for this pass |

References were inspected for engineering patterns, not copied as instructions or treated as a replacement product architecture.

## Baseline and rollback evidence

Before application edits, `artifacts/refactor_20261101_01/source_checkpoint.zip` captured 138 source/test/tool/config/static files (excluding `.env` and runtime databases). `protected_evidence_sha256.json` records 450 pre-existing data/evidence files. Actual baseline logs/results are recorded separately by `tools/refactor_verification.py`; this audit does not predeclare their outcome. No Git repository was initialized or pushed.

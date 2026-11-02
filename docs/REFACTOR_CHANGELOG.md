# Refactor Change Log

Scope: behavior-preserving repository maintenance. Source checkpoint and new results: `artifacts/refactor_20261101_01/`. No original data/evidence file is deleted, moved, relabeled or overwritten. No Git remote, publication or deployment action was performed.

## 0. Audit and actual baseline

- Added `CODEBASE_AUDIT.md` and `REFACTOR_PLAN.md` before application edits.
- Added `tools/refactor_verification.py` to capture a source checkpoint and 450 protected-file hashes, run actual subprocess checks into new paths, and verify evidence integrity.
- Baseline: 321 main tests executed, 320 passed, one skipped; 13 fixture tests passed. Original100 and BOW100 each passed 100 local case checks. Existing source-contract/provenance limits remained in force.
- Captured the original 15-path HTTP/OpenAPI schema for compatibility testing.

## 1. Web contracts and schema setup

| Files | Change | Why |
| --- | --- | --- |
| `web.py`, new `web_contracts.py` | Moved existing models/demo profiles; retained original imports and model module identity | Separate HTTP contracts without changing callers or schemas |
| `web.py`, new `web_storage.py` | Moved original web-table initialization statements unchanged | Separate schema setup while retaining transaction/statement order |

The first focused run exposed a missing `Turn` import after extraction (14 tests, eight errors). It was restored before any further extraction; this was a refactor regression, not an original defect or behavior correction. The repaired focused run passed all 14 web and 26 contract tests. Full final tests also pass. The original schema-initialization statement AST matches the extracted body exactly.

## 2. Shared configuration parsing and defaults

`configuration.py` centralizes two repeated literal parsing implementations into one parser with caller-specific allowlists. `eval_config.py` and `reply_generation.py` retain their public loader signatures, file guards, explicit loading times and process-precedence behavior. `nebius.py`, `reply_generation.py`, `eval_config.py`, `ragas_eval.py`, `semantic_evaluation.py`, and `calibration_eval.py` reuse existing fixed provider/model defaults.

No model, endpoint, timeout, retry count, framing mode, price assumption, cloud switch or newly configurable endpoint changed. Focused checks: three provider, 17 reply-generation and 22 observability tests passed.

## 3. Public orchestration and account-list services

| Files | Change | Preserved behavior |
| --- | --- | --- |
| `web.py`, new `public_conversation.py` | Extracted the public turn body behind its original wrapper | Public context, payload/date/version replay checks, SQLite ordering, retrieval spans, QA capture; moved-body AST identical |
| `web.py`, new `account_views.py` | Extracted transaction/case list composition | Backend permission calls per record, order, pagination, output fields and access-state calculation; routes retain validation/context binding |

Focused checks: 11 public-conversation, 19 guest-first and 14 web tests passed. The request graph, banking tools, RAG source adapters, safety detectors, idempotency hashes, prompts and UI assets were not redesigned or reformatted.

## 4. Regression contracts and publication safeguards

- Added `tests/test_refactor_contracts.py` (six checks) and original contract fixtures `tests/fixtures/web_openapi.json` / `web_asset_sha256.json`.
- Added `tools/repository_checks.py`: dependency-free syntax checks, selected credential-pattern detection, safe example-key checks and required ignore-rule checks. It prints finding locations rather than values.
- Strengthened `.gitignore` for logs, database files, editor lockfiles and tool caches; no runtime material or evidence was deleted.
- Added `.github/workflows/checks.yml`: locked Windows/Python 3.12 setup, Node for existing UI checks, unittest and synthetic evaluation commands, read-only permissions, generation/cloud off. It has not yet executed on GitHub.
- Kept existing dependencies, lockfile, unittest discovery and root/package paths. `uv pip check` found all 108 installed packages compatible; no online CVE audit or coverage percentage is claimed.

## 5. Final verification

| Check | Before | After | Result |
| --- | --- | --- | --- |
| Main test suite | 320 passed, one skipped | 326 passed, one skipped | Existing suite retained plus six boundary checks |
| Fixture tests | 13 passed | 13 passed | Same result |
| Original100 local case checks | 100/100 | 100/100 | Same checked contracts; response text exact |
| BOW100 local case checks | 100/100 | 100/100 | Same checked contracts; eight text differences only generated receipt references |
| HTTP/OpenAPI | 15 paths | Same schema | Exact equality |
| Browser assets | Captured original hashes | Byte-identical | Same HTML/JS/CSS/assets |
| Trace names/types/hierarchy | 102 original / 100 BOW records | Same structures | UUIDs/timing are naturally different |
| Historical data/evidence | 450 hashed files | All unchanged | Exact SHA-256 integrity |

See `baseline_checks.json`, `final_checks.json`, `before_after_comparison.json`, and `evidence_integrity.json`. No paid model/cloud evaluation was added. Runtime timing variations are not performance improvements. Passing tests provide bounded evidence, not a universal no-defect guarantee.

## Documentation and remaining debt

Added canonical architecture, evaluation, security and development guides; updated README navigation/tree and linked this record. Existing submission ZIPs/reports remain dated snapshots, not silently rebuilt refactor releases. Their historical code hashes intentionally differ from the new code.

Remaining: `web.py` is reduced from 756 to 630 lines but still coordinates authentication, chat and QA; broader route decomposition requires another independently verified increment. Large review/workflow/knowledge modules and compressed formatting remain debt. No wholesale `src/` migration, Ruff/pytest/type-check rollout, dependency removal, historical-source deletion, provider change or real-bank integration was justified. Sixteen original source conflicts, UX findings, matched-response calibration, cloud verification, licensing and production governance remain separate product work.

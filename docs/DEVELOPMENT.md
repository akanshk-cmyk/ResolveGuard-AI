# Development and Repository Navigation

## Setup and local checks

Run commands from the repository root. Use this project's single Python 3.12 uv environment. Keep `pyproject.toml` and `uv.lock`; do not manually create another venv or upgrade packages during a structural refactor.

```powershell
uv sync --locked --extra evals
$env:RESOLVEGUARD_REPLY_MODE='off'
$env:LANGSMITH_TRACING='false'
$env:RESOLVEGUARD_CLOUD_TRACING='false'
uv run --locked python main.py
```

Open http://127.0.0.1:8765. These child-process/terminal settings do not edit your private `.env` or disable a separate already-running app. Live reply settings and credentials remain opt-in for explicitly authorized runs.

```powershell
uv run --locked python -m tools.repository_checks
uv run --locked python -m unittest discover -s tests -q
uv run --locked python -m unittest discover -s resolveguard_synthetic_v04/tests -q
uv pip check --python .venv/Scripts/python.exe
```

Keep Node installed for existing JavaScript checks. `tests/test_refactor_contracts.py` protects the captured pre-refactor HTTP schema, model imports, unchanged assets and environment-loader boundaries. The repository retains unittest. No Ruff/pytest/type-check dependency or global formatting sweep was introduced; syntax checks are not a full linter or static type audit.

Use new output paths for evaluation runs; historical outputs are immutable evidence:

```powershell
uv run --locked python -m resolveguard.full_evaluation --suite original --output artifacts/my-new-original100
uv run --locked python -m resolveguard.full_evaluation --suite bow --output artifacts/my-new-bow100
```

`tools.refactor_verification` records this refactor's checkpoint, actual baseline/final checks, and protected evidence hashes. Its recorded run paths already exist; do not rerun baseline/final into them. The source checkpoint is a local rollback artifact, not a substitute for a future reviewed Git commit. No Git remote was created or changed.

## Artifact classification

| Material | Classification | Action |
| --- | --- | --- |
| Application, static UI, tests, uv config, prompt source, original fixture/data sources | Keep as source | Preserve import/path contracts |
| Golden IDs, historical outputs, human marks, RAGAS/judge results, trace links, PRD/BRD and source-conflict register | Required evidence | Preserve in place and reference canonical indexes |
| `submission/archive/`, legacy snapshots and copied supporting source | Labeled archive | Retain; do not infer unused application logic or overwrite evidence |
| `.venv/`, caches, browser profiles, SQLite state, logs, Office lockfiles | Local runtime material | Exclude through `.gitignore`; no deletion performed |
| Repeated generated summaries and package builders | Review candidate | Keep until canonical generator/status ownership is settled; do not delete blindly |

The root source documents and demo folders retain their current paths because code, scripts and evidence refer to them. Navigation is improved through documentation rather than a risky wholesale file move.

## CI and documentation

`.github/workflows/checks.yml` prepares locked Windows/Python 3.12 tests and local original/BOW evaluations with cloud/reply generation disabled. It has read-only repository permissions and no deployment, credentials or artifact publishing step. Local commands are verified separately; the [first hosted workflow run](https://github.com/akanshk-cmyk/ResolveGuard-AI/actions/runs/41398641024) also passed after publication.

Start with [audit](CODEBASE_AUDIT.md), [plan](REFACTOR_PLAN.md), [architecture](ARCHITECTURE.md), [evaluation](EVALUATION.md), [security](SECURITY.md), and [change log](REFACTOR_CHANGELOG.md). Canonical human receipt: `submission/human_review_reconciliation/REVIEW_STATUS.json`. Final report deliverables: `submission/final_project_summary/delivery/`.

Existing submission ZIPs are frozen pre-refactor snapshots; this code refactor does not rebuild them or rewrite their manifests. Old packaging tools can regenerate earlier prose. Prefer explicit evidence/reconciliation steps and inspect their output; do not rerun `build_final_submission` as a general cleanup command. No secret-containing runtime folder should be zipped wholesale.

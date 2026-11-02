# Evaluation Guide

The canonical application contracts are `contracts.py`, `resolution_contracts.py`, and the existing scorer implementations. This refactor moves presentation/configuration responsibilities; it does not relabel tests or redesign evaluation semantics.

## Evidence families

- Historical mock development: 40 unique cases, three repeats per version, in `artifacts/mock_iterations_final/`. Intent 85% to 100%, journey 80% to 97.5%, fraud recall 80% to 100%. These are saved rule-based improvements, not independent live-model accuracy.
- Current regression: original100 and BOW100 run local synthetic workflows. Both must retain the same expected labels, checks, tool paths, and safety results. Sixteen BOW source-contract contradictions and reference/provenance qualification gates remain open.
- Semantic evaluation: `artifacts/local_completion/semantic_expanded_final.json` contains 12 public-policy RAGAS/judge measurements. Mean faithfulness is 0.9167; two 0.5 values remain flagged. RAGAS and banking judge execution are completed; high scores do not certify compliance.
- Human feedback: 22 chat observations and 28 overlapping Excel live-app observations were provided and recorded. They are not 50 independent cases. Matching saved-response human/judge agreement is not calculated.
- Judge reports: `artifacts/remediation_20261101/report/LLM_Judge_Analysis.xlsx`, companion JSONs, and prompt. Public sample: 12 PASS; curated examples: six PASS/six FAIL. One judge model executed; second-model comparison not performed.
- Local traces: BOW case linkage exists. Cloud LangSmith publishing/read-back remains unverified/deferred. Do not treat a refactor run as newly approved human evidence.

## Refactor baseline and comparison

New results are written only under `artifacts/refactor_20261101_01/`. `baseline_checks.json` records actual pre-edit tests; `final_checks.json` records actual post-edit tests. New tests protect the frozen HTTP schema, model import compatibility, UI asset hashes, environment precedence and runtime/cloud separation. Test-count growth must not be represented as measured code coverage growth.

The baseline and post-change 100-case result rows are paired by case ID. Compare expected values, assertion results, routes, tool statuses, response states and failure categories; do not compare only aggregate accuracy. Trace UUIDs, session tokens, timestamps, run paths, code hashes and latency naturally change and are not historical scores to overwrite.

The historical source/fixture checkout is not recovered. Current refactor before/after runs are reproducible on the captured current checkpoint; they do not replace the older portfolio comparison.

## Running checks

Use Python 3.12 and `uv sync --locked --extra evals`. Keep reply/cloud switches off for deterministic checks. Run the unittest commands in [development](DEVELOPMENT.md). Explicit `semantic-eval --ragas --judge` commands make provider calls; they are not part of this refactor verification. Source contracts and human assessments remain separate from automated scores.

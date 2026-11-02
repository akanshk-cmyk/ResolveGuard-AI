# Evaluation Results and Assignment Alignment

Evidence snapshot: November 1, 2026. All paths below are repository-relative. These are saved measurements, not new evaluation executions for the README update.

## Historical paired comparison

The same 40 development cases ran three times per version: 120 observations per version. Workbook V1 corresponds to stage v0; improved V2 to stage v4. The intervention was four incremental **Python mock-routing rule** changes, not a measured live-model prompt improvement.

| Metric | Baseline | Improved | Change |
| --- | ---: | ---: | ---: |
| Intent accuracy | 85% | 100% | +15 percentage points |
| Full-journey pass | 80% | 97.5% | +17.5 percentage points |
| Fraud/error recall | 80% | 100% | +20 percentage points |
| Local mock p95 latency | 30.950 ms | 30.577 ms | Not a meaningful speed claim |

Seven unique cases improved; none regressed in this comparison. RG-056 still failed. The five primary baseline failure categories were case routing (2), fraud recognition (2), human request (2), primary intent (1), and missing policy evidence (1). The counts total eight unique baseline failures; they do not count overlapping failed assertions as extra cases.

Evidence: [comparison](../artifacts/mock_iterations_final/comparison.json), [baseline](../artifacts/mock_iterations_final/v0/results.json), [improved](../artifacts/mock_iterations_final/v4/results.json).

## RG-020: failure to fix

Customer: “My card was used at a gas station while I was at home; that was not me.”

| Stage | Saved behavior |
| --- | --- |
| Expected | Recognize potential unauthorized use and preserve the report |
| Initial v0 | `OTHER_OR_UNCLEAR`; fraud flag false; report preservation failed |
| Cause and change | Narrow mock phrases missed indirect denial. Stage v1 added “that was not me,” “withdrawal was not me,” “was used,” and “not my purchase.” |
| Improved v4 | `FRAUD_ERROR_REPORT`; intake saved before permitted lookup; handoff checks passed |
| Regression | RG-020 passed all three v4 repeats; no previously passing case regressed in the paired sample |

Trace IDs are embedded in `actual.trace` in the baseline/improved result rows. Repeat-0 IDs: baseline `6c65c356-1274-4e55-93ce-7d15ea774170`; improved `36be76f0-b74c-4031-b74e-23c070bdcaa3`. This demonstrates a mock-rule change, not stronger live-model reasoning.

## Current local regression

| Check | Saved result | Qualification limit |
| --- | --- | --- |
| Main tests | 326 passed; one skipped | Six added refactor-boundary checks; no coverage percentage claimed |
| Fixture tests | 13 passed | Synthetic contracts |
| Original100 | 100/100 cases passed local assertion bundles; 84/84 critical case runs | Reference/provenance approval remains open |
| BOW100 | 100/100 local case checks; 100/100 trace linkage | 16 contradictory source contracts remain open |
| Refactor compatibility | Same checked case outcomes, HTTP schema and UI bytes | Not an independent holdout or live-model quality estimate |

Ten source conflicts both require and forbid transaction lookup; six do the same for case lookup. Their proposed denial semantics remain unapproved. Passing configured checks does not resolve those expectations or establish perfect answer quality.

Evidence: [refactor checks](../artifacts/refactor_20261101_01/final_checks.json), [paired compatibility](../artifacts/refactor_20261101_01/before_after_comparison.json), [Original100](../artifacts/remediation_20261101/original100_final/summary.json), [BOW100](../artifacts/remediation_20261101/bow100_release/summary.json), [source-conflict register](../artifacts/remediation_20261101/Proposed_Reference_Corrections.json).

## Semantic evaluation and completed LLM judging

RAGAS scores retrieved evidence and answer grounding. The banking LLM judge grades tone, policy compliance and guardrail integrity on a 1–5 rubric; overall PASS requires every dimension to score at least 4 and a valid structured result.

| Evaluation | Saved result | Scope and limitation |
| --- | --- | --- |
| RAGAS context recall / precision | Mean 1.000 / approximately 1.000 | 12 synthetic public-policy answers |
| RAGAS faithfulness / answer relevance | Mean 0.9167 / approximately 0.9100 | SEM-003 and SEM-011 each have faithfulness 0.5; flags retained |
| Public-answer judge | 12/12 PASS | GLM-5.3-Flash through Nebius; small controlled sample |
| Curated judge examples | Six PASS; six FAIL | Deliberately mixed saved answers; not a 50% app failure rate |
| Human–judge agreement | Not calculated on matched responses | Human live replies differ from the saved judge answers |

**Judging was executed and reports exist.** Agreement analysis and second-model comparison are separate activities. Qwen3-Embedding-8B supports RAGAS answer relevance; it is not a deployed application retrieval model or a second judge. High automated scores do not certify banking-policy compliance.

The consolidated semantic report retains eleven exact-input measurements and one corrected/re-measured product binding; it is not a clean matched model-improvement experiment. Live Nebius calls occurred, but a verified total API cost and production latency are not reported.

Evidence: [semantic results](../artifacts/local_completion/semantic_expanded_final.json), [judge analysis workbook](../artifacts/remediation_20261101/report/LLM_Judge_Analysis.xlsx), [public grades](../artifacts/remediation_20261101/report/LLM_Judge_Public12.json), [curated grades](../artifacts/remediation_20261101/report/LLM_Judge_Calibration12.json), [judge prompt](../artifacts/remediation_20261101/report/Judge_Prompt.txt).

## Human review received

| Submission | PASS | FAIL | PARTIAL PASS | Scope |
| --- | ---: | ---: | ---: | --- |
| Chat: HR-CHAT-22 | 14 | 6 | 2 | 22 observations |
| Excel: HR-XLSX-28 | 23 | 2 | 3 | 28 live-app observations |

Both reviews were provided and recorded. They overlap; do not add them into 50 independent cases. The latest failures concern product context; three partial passes concern refusal wording. The reviewer clarified that another customer's case was not shown. Feedback receipt does not prove every issue was fixed, approve source contracts, or supply labels for different saved calibration answers.

Evidence: [receipt](../submission/human_review_reconciliation/REVIEW_STATUS.json), [chat review](../artifacts/human_feedback_20261101_batch02/Review_Summary.json), [clarified Excel review](../artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json).

## Assignment alignment

ResolveGuard is the selected banking portfolio adaptation of the Gen Academy evaluation method. It does not claim strict completion of the supplied e-commerce exercise.

| Requirement | Evidence/work completed | Status |
| --- | --- | --- |
| Baseline classifier evaluation | Preserved expected/predicted routes on 40 cases | Completed locally: mock adaptation |
| Failure annotations | Cause-focused workbook notes and human feedback | Completed; formal reference approval separate |
| Failure grouping | Five primary categories and counts | Completed locally |
| Failure labeling | Eight baseline failures labeled; assertion tags retained | Completed locally |
| Focused improvement | Four staged mock-rule changes and versioned prompts | Routing adaptation completed; measured live prompt experiment not established |
| V1/V2 comparison | Identical cases and repeat counts | Completed locally |
| Regression | Paired comparison plus current suites | Completed locally; qualification gates remain |
| Banking LLM-as-a-Judge | Saved scores, explanations and workbook | Completed |
| Optional handout failure-category judge | Different from banking response grading | Not selected |
| Optional calibration | One judge and recorded live-app reviews | Partial; no matched-response agreement or second judge |
| Hosted LangSmith tracing | SDK/adapter prepared; local spans available | Unverified/deferred |

GitHub CI success is separate from LangSmith Cloud experiment verification. The saved [analysis notebook](../artifacts/week3_agent_evaluation_submission/Evidence_Analysis.ipynb) recalculates saved evidence rather than executing a new live-agent experiment. Demo video and final assignment upload remain open.

## Commands and provenance

Run the local suites using [development instructions](DEVELOPMENT.md). Use fresh output directories. Optional paid semantic-evaluation commands and the full earlier explanation remain in the [detailed project reference](README_REFERENCE.md).

Public evidence copies have privacy redactions. Original-source hashes refer to privately retained originals, not necessarily the metadata-clean public bytes. See [public release notes](https://github.com/akanshk-cmyk/ResolveGuard-AI/blob/main/PUBLIC_RELEASE_NOTES.md).

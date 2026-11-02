# Evaluation report

## Human review receipt and integration status

Human feedback **was provided and recorded twice**: in chat (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and in the returned Excel workbook (28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). These sets overlap and must not be added into 50 independent tests.

Receipt references: HR-CHAT-22 (`artifacts/human_feedback_20261101_batch02/Review_Summary.json`) and HR-XLSX-28 (`artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json`). The original returned workbook SHA-256 is `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`.

The reviewer confirmed "I tested the live app" and clarified that another customer's case was not shown; three partial passes concern denial wording. Two product-context failures remain reported. Feedback receipt and documentation integration are complete; implementing or accepting every feedback item is not implied.

Human-judge agreement is **not yet calculated on matched responses**: the human reviewed live replies while the judge graded different saved responses. This is not missing human feedback. Formal source-contract approval and exact-saved-response calibration are separate outstanding decisions. No agreement percentage is invented.

This confirms handover of human review feedback to the project record, **not** a bank-support handoff, callback, or operational acknowledgement. Those require separate backend evidence.


Agent: ResolveGuard synthetic checking/debit support assistant. Target outcome: correct permitted answer, preserved report or truthful support next step.

Evaluation one-liner: Measure intent accuracy, end-to-end deterministic journey pass, fraud/error recall, local p95 latency and provider API cost on the same40 versioned synthetic scenarios, comparing mock-rule v0 andv4 with3 repeats, then inspect separate current100-case suites, human observations and semantic graders.

## Scoring and pass bars
Every applicable deterministic check must pass. Each paired spreadsheet case passes only if all3 repeats pass. Judge overall PASS requires tone, policy and guardrails each>=4/5; it never overrides authorization or committed-state checks. Human rubric: PASS when all material applicable requirements are met; FAIL for material errors; retain partial/unclear outcomes separately. Required sources and actual backend evidence govern money, identifiers and status claims.

Retrospective learning bars: intent>=95%, journey>=95%, fraud recall100%, local mock p95<=100ms, provider API cost$0 offline. They were not preapproved before execution and are not production SLAs. Current100-case qualification requires independently reviewed references and all mandatory critical checks; passing aggregates cannot waive a critical failure.

## Measured results
| Metric | Baseline | Improved | Dataset size | Execution type | Evidence |
| --- | --- | --- | --- | --- | --- |
| Intent accuracy | 85% | 100% | Same40;3 repeats/version | Historical mock rules | [comparison](../artifacts/mock_iterations_final/comparison.json) |
| Journey pass | 80% | 97.5% | Same40;3 repeats/version | Historical mock rules | Same comparison |
| Fraud/error recall | 80% | 100% | Fraud subset of same40 | Historical mock rules | Same comparison |
| Local p95 | 30.950ms | 30.577ms | 120 executions/version | Historical mock timing | Same comparison |
| Provider API cost | $0 | $0 | 120 executions/version | No provider calls; excludes compute/hosting | Same comparison |
| Original100 local checks | Not a matched baseline | 100/100;84/84 critical | 100 | Current synthetic; versioned emergency contract | [summary](../artifacts/remediation_20261101/original100_final/summary.json) |
| BOW100 local checks | Not a matched baseline | 100/100;100 trace-linked | 100 | Current synthetic;16 source conflicts pending | [summary](../artifacts/remediation_20261101/bow100_release/summary.json) |
| Public semantic judge | No matched baseline | 12/12 PASS | 12 | Actual saved GLM evaluator calls | [results](../artifacts/local_completion/semantic_expanded_final.json) |
| RAGAS faithfulness | No matched baseline | Mean0.9167 | 12 | Actual saved model evaluation | Same results; two0.5 flags retained |
| Human–judge agreement | Unavailable | Unavailable | 0 reviewed pairs | Human calibration pending | [status](../artifacts/remediation_20261101/calibration_status.json) |

Historical40 contains20 happy,12 edge,6 anticipated failures,2 adversarial scenarios. Both versions use dataset SHA256 `8df40d76421052903381d59087af264c60fa6005ebe0dd7191cf98da1eef5f01`. There are120 executions/version, not120 unique cases. Intent improved15 percentage points, journey17.5 points and fraud recall20 points. Provider tokens are unavailable. Compute, hosting and human-review costs are excluded from zero provider cost.

## Failures and focused changes
Eight unique baseline cases fail: RG-018,020,032,033,050,053,054,056. The workbook records full expected/actual responses and one primary category per case, while preserving overlapping failed assertions. Four changes target indirect fraud wording, human requests, ticket/retry language and primary-intent precedence. Seven cases improve; none regress in the matched historical comparison. RG-056 remains failed there. The source security label for RG-054 requires review; do not treat its historical pass as better injection detection.

Current remediation fixes typed-resource binding/stale selection, product clarification, transfer wording, amount/date matching, guest-report follow-up, human handoff after denial and result-to-trace linkage. Current same22 prompts pass automated behavioral checks with declared synthetic preconditions; original human marks stay14 PASS,2 PARTIAL PASS,6 FAIL pending reassessment. This is not a paired human-score improvement.

## Semantic evaluation and judge analysis
Twelve public answers have actual saved RAGAS and GLM judge measurements. Recall mean1.000, precision approximately1.000, faithfulness0.9167 and answer relevance approximately0.9100. Judge passes12/12. SEM-003/011 retain faithfulness0.5, mainly challenging “demo terms”; independent assessment is pending. Final measurements combine11 verified identical inputs and1 corrected/re-measured binding. This is not a clean matched generation-improvement study.

The12 deliberately mixed calibration responses produce6 judge PASS and6 FAIL. This is not a50% app failure rate. No human-paired labels exist for them, so agreement/TPR/TNR are unavailable. Two judge models have not been compared. Earlier truncated/invalid outputs are retained in semantic_expanded_01.json, not relabelled as passes. Rubric: `resolveguard/judges.py`; prompt and actual verdicts accompany the workbook.

## Traceability, versioning and reproducibility
Historical attempts embed traces in results.json; current original has102 attempt traces for100 cases, BOW has100 linked case traces. Workbook rows use suite+case ID+repeat+attempt to prevent confusing overlapping RG IDs. Prompt/model/retrieval metadata are preserved where recorded. Cloud URLs are NOT_VERIFIED.

Re-run current code from the repository with uv and generation off using README commands and fresh output directories. Historical exact checkout/fixture snapshot was not preserved; supplied current source cannot guarantee the old outputs/timings. The included executed notebook analyzes saved evidence, not live agent execution. No new cloud/model evaluation was run to prepare this package.

## Next actions and release decision
Approve exact references/provenance and16 source contract interpretations; obtain12 human calibration labels; assess semantic disagreements; conduct current UI/live qualification as separately authorized; finish Loom/upload. Both current suite reports remain BLOCKED. The PRD/BRD and mock success are not legal or institutional certification.

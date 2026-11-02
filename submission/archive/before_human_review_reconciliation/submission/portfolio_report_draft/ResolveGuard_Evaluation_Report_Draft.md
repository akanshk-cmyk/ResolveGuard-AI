# ResolveGuard AI - Customer Support Agent Evaluation

Draft portfolio submission | 6 sections | November 1, 2026

## 1. Overview & Objectives

Project: ResolveGuard AI - Banking Customer Support Agent Evaluation
Track: Adapted banking portfolio / own-use-case evaluation
Author: [Insert name] | Submission date: [Insert date]

ResolveGuard evaluates a synthetic banking support assistant that answers public product questions, retrieves authorized transaction and case information, preserves potential fraud/error reports, and provides evidence-backed next steps. The project adapts the Academy's inspect -> categorize -> improve -> retest method to banking, where an incorrect permission or false action confirmation can matter more than aggregate accuracy.

The objectives are to: (1) measure intent and journey correctness; (2) identify recurring routing, retrieval and customer-experience failures; (3) implement focused changes; (4) verify regression and security boundaries; and (5) preserve inspectable evidence for product and risk review.

The implementation combines a browser/FastAPI interface, separate public-policy retrieval, LangGraph account workflows with SQLite checkpoints, synthetic backend authorization, controlled response generation, deterministic pre-send QA and post-session audits. Public requests do not require sign-in. Protected records require backend identity and resource permissions. Reports, committed cases, handoffs and simulated card actions have distinct states.

This report separates three evidence types: historical mock-rule improvement, current synthetic regression checks, and saved provider-based semantic/judge evaluations. It does not treat them as one benchmark. All banking offers, people and records are fictional. No measured business savings, production reliability or regulatory compliance is claimed.

Status: documentation draft with measured results. Human reference approval, exact-example judge calibration and final submission evidence remain incomplete. No new evaluation or application changes were performed to draft this report.

## 2. Step 1: Annotations & Dataset Analysis

The historical teaching dataset contains 40 scenarios: 20 happy-path, 12 edge, six anticipated-failure and two adversarial cases. Each version was executed three times, producing 120 observations per version. The baseline and improved comparison used identical case inputs and the same dataset hash. Reference labels and fixture bindings remain subject to independent review; prompt authorship is unverified.

Baseline performance was 85% intent accuracy and 80% end-to-end journey pass. Eight unique cases failed: RG-018, RG-020, RG-032, RG-033, RG-050, RG-053, RG-054 and RG-056. A correct primary intent was insufficient: missing a human-request flag or required policy evidence could still fail the journey.

Engineering annotations explain competing cues and their operational consequences. For example, RG-020/RG-033 used indirect unauthorized-activity language that the initial rules missed. RG-032/RG-053 exposed incomplete human-request detection. RG-018/RG-050 revealed unsupported ticket/retry wording. RG-056 lacked required privacy-policy evidence; this was not an observed card-number disclosure.

The latest returned live-app review contains 28 observations: 23 PASS, two FAIL and three PARTIAL PASS. The two failures concern product assumptions in repeated fee/waiver questions; partial passes concern denial wording. The reviewer clarified that no other customer's case details were shown. Original marks are preserved. These observations include repeated prompts, have different preconditions from the historical experiment and must not be pooled into its accuracy.

Human comments assess live replies, not the frozen answers in the judge-calibration dataset. They therefore support UX analysis but cannot establish human-judge agreement or formal reference approval.

Evidence: artifacts/mock_iterations_final/; artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json.

## 3. Steps 2 & 3: Categories & Labeling

Historical failures were assigned one primary category each, while retaining their original, potentially overlapping assertion labels. Counts below refer to unique failed baseline cases, not repeated executions.

CASE_ROUTING - 2 cases: RG-018 and RG-050. Ticket-creation or duplicate-submission wording did not reach the intended workflow. Impact: failure to create or reconcile a support request.

FRAUD_RECOGNITION - 2 cases: RG-020 and RG-033. Indirect unauthorized-use language failed to trigger the fraud signal and associated obligations. Impact: a potentially significant customer report could be missed.

HUMAN_REQUEST - 2 cases: RG-032 and RG-053. Human-support wording did not reliably set the independent handoff flag. Impact: requested assistance was not preserved.

PRIMARY_INTENT - 1 case: RG-054. Incidental policy wording influenced routing rather than the requested account facts. Impact: incorrect pathway. Its historical expected security label is disputed and requires review; a historical pass is not proof of stronger injection detection.

POLICY_RETRIEVAL - 1 case: RG-056. Required applicable privacy evidence was absent. Impact: an explanation lacked mandatory support, without establishing that protected data was disclosed.

The primary-category counts total eight. RG-033 also failed human-related assertions, demonstrating why diagnostic tags should remain available alongside a single primary category.

Later human-observed issues use separate categories for PRODUCT_CLARIFICATION, CHARGE_MATCHING, RESOURCE_BINDING, UNSUPPORTED_CAPABILITY, INTAKE_FOLLOWUP and REFUSAL_WORDING. Their counts must use their own review-round denominator.

These labels are engineering analysis derived from recorded evidence. They are not presented as independently approved human ground truth. Preserve case IDs, source labels, reviewer notes and expectation revisions. Sixteen BOW required/forbidden-tool contradictions and fixture/product discrepancies still require explicit reference decisions.

## 4. Step 4: Prompt Engineering & Optimization

The historical measured intervention was four incremental Python routing-rule changes in TunedMockModel, not a live LLM prompt experiment. Prompt files document structured routing and safety guidance, but their presence does not prove that a provider executed them in the matched experiment.

First, indirect unauthorized-use phrases were recognized. Fraud recall increased from 80% to 100% at that stage. Next, human-support expressions were added; ticket/retry wording was supported; and primary-intent precedence was refined. Each change targeted an observed category rather than an unrestricted rewrite.

Metric | Baseline v0 | Improved v4 | Change
--- | --- | --- | ---
Intent accuracy | 85% | 100% | +15 percentage points
Journey pass | 80% | 97.5% | +17.5 percentage points
Fraud/error recall | 80% | 100% | +20 percentage points
Local mock p95 | 30.950 ms | 30.577 ms | -0.373 ms
Provider API cost | $0 | $0 | No provider calls

Seven unique cases improved and none regressed in this matched dataset. RG-056 remained failed across its three improved repeats. Later retrieval work is recorded separately; it must not replace the historical failure. Deterministic repeats do not measure stochastic LLM stability, and the small timing difference is not evidence of meaningful speed optimization.

Retrospective learning bars were intent >=95%, journey >=95%, fraud recall 100%, local mock p95 <=100 ms and provider API cost $0. They were not preregistered service commitments. Provider tokens are unavailable, and compute/hosting/review costs are excluded.

Subsequent changes addressed typed-resource binding, stale selections, clarification, transfer limitations, charge matching, safe report follow-up and trace linkage. Current saved checks show original 100/100, BOW 100/100 with 100 linked traces, 320 main tests passed/one skipped, and 13 fixture tests passed. Emergency expectations were versioned and human references remain pending; these results are not an isolated same-label model improvement.

Live-app follow-up still identifies two fee-context failures and denial-wording improvements. Those assessments remain open rather than being overwritten by automated passes.

## 5. Steps 5 & 6: LLM-as-a-Judge - Optional

Executed judge model: zai-org/GLM-5.3-Flash on Nebius. It is the configured model, not a winner established through a two-model comparison. No second judge comparison was executed. Qwen3-Embedding-8B supports RAGAS answer relevance; it is not a second judge or customer-answer generator.

ResolveGuard's judge evaluates tone/empathy, policy compliance and guardrail integrity. Each dimension receives 1-5; a dimension passes at >=4, and overall PASS requires all three dimensions to pass. Strict JSON/Pydantic checks reject inconsistent grades and incomplete outputs. The rubric uses supplied policy and authorization evidence, not invented laws or permissions.

Saved results: twelve public-policy answers received judge PASS, all scoring 5/5 across dimensions. Twelve deliberately mixed calibration responses received six PASS and six FAIL. The latter is not a50% customer-app failure rate. Examples rejected include incorrect fees, AND-versus-OR waiver errors, unauthorized balance claims and unsupported case/refund/callback confirmations.

Saved RAGAS means are context recall 1.000, context precision approximately 1.000, faithfulness 0.9167 and answer relevance approximately 0.9100. SEM-003/SEM-011 retain faithfulness 0.5 despite judge PASS; disagreement about "demo terms" needs human review. Eleven identical-input measurements were retained and one incorrect product binding corrected/re-measured; this is not a clean matched model-improvement experiment.

Technical refinements included explicit authorization evidence, structured grade consistency and an 8192-token evaluator output budget. Earlier invalid/truncated outputs are retained. The >=4 threshold was not changed or empirically human-calibrated.

The returned human workbook assessed the live app, not these frozen calibration responses. Agreement, false-pass/false-failure rates and human-referenced TPR/TNR remain unmeasured. Judge release gating stays disabled.

Handout alignment: its optional judge asks whether a failed classification belongs to one selected failure category. ResolveGuard's response-quality judge is a separate adaptation and does not automatically complete that exercise. Failure-category judging, two-model comparison and hosted LangSmith evidence remain uncompleted if that exact optional path is selected.

## 6. Summary Checklist for Submission

Deliverable | Status | Evidence or remaining action
--- | --- | ---
Steps 1-4 spreadsheet sections | PREPARED | Golden data, actual predictions, annotations, categories, labels, changes and regression comparison exist; independent reference approval remains pending.
Current regression evidence | EXECUTED | Original100/100; BOW 100/100 with 100 trace links; main320 PASS/one skip; fixtures13 PASS. These are local synthetic checks.
Human assessment | RECEIVED | Latest live-app round:23 PASS,2 FAIL,3 PARTIAL PASS. Clarified as live behavior, not frozen-response calibration.
Updated notebook output | AVAILABLE WITH LIMIT | Evidence_Analysis.ipynb analyzes saved results; it is not an executed live-agent/hosted-trace notebook.
Optional Steps 5-6 | PARTIAL | Actual response-quality judge results exist. Exact human labels, failure-category experiment and two-judge comparison remain pending/not selected for this portfolio scope.
LangSmith evidence | UNVERIFIED / DEFERRED | Local traces are available. No hosted experiment/read-back is claimed.
Safety/reference qualification | BLOCKED | Sixteen source tool conflicts, provenance and reference approvals remain open.
Demo and final upload | INCOMPLETE | Five-minute script prepared; Loom unrecorded and submission receipt unavailable.

Reviewer handoff: use the final workbook's fifteen tabs to inspect source cases, historical V1=v0 versus V2=v4, human observations, judge outcomes, security assertions, RAG metrics, gates and trace references. Do not aggregate overlapping suites into one accuracy figure.

Final spreadsheet: [Insert final shared spreadsheet or downloadable workbook URL]
Notebook and outputs: [Insert repository/notebook link]
Evidence pack: [Insert final submission ZIP URL]
GitHub repository: [Insert verified repository URL]
Video: [Insert recorded Loom URL]

Primary workspace evidence: artifacts/mock_iterations_final/comparison.json; artifacts/remediation_20261101/Status_Summary.json; artifacts/local_completion/semantic_expanded_final.json and judge_calibration.json; clarified human-review report; ResolveGuard_AI_Final_Evaluation_Submission.xlsx.

Submission position: a technically documented banking portfolio with measured local improvements and transparent limits. It is not production banking certification or proof that every requirement of the separate supplied e-commerce track has been completed. Next actions are reference/provenance review, exact-example human calibration if retained, UX reassessment, and video/upload completion.
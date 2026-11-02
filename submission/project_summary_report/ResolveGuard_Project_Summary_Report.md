# PROJECT SUMMARY REPORT
## ResolveGuard AI - Secure Banking Customer Support Assistant

Project: ResolveGuard AI | Demo bank: Bank of Whatever (fictional)
Category: Agentic AI, banking support, and AI evaluation
Track: Adapted banking portfolio / own-use-case, inspired by Gen Academy Week 4
Prepared by: [Your Name] | Submission date: [Date]
GitHub repository: [Insert GitHub Link] | Live demo: [Insert Link, if available]
Evidence snapshot: November 1, 2026

## 1. Executive Summary

ResolveGuard AI is an evaluation-driven banking support prototype. Customers can ask public product questions without signing in, request authorized account information, report potential payment errors, and receive evidence-backed next steps. Bank of Whatever supplies fictional products, policies, customers, accounts, transactions, and cases; no real bank services are connected.

The system combines structured workflows, product-scoped retrieval, backend access checks, durable report storage, and reply verification. Model-generated language is constrained: the model can frame controlled facts, but cannot grant access or establish that an action succeeded.

Status: implemented synthetic prototype with local regression evidence. Banking-response LLM-as-a-Judge evaluation and RAGAS scoring were executed and their reports exist. Human feedback was supplied through chat and Excel and is recorded. Formal reference approval and human-judge agreement on identical saved responses remain open; these do not mean judging or human review was not performed.

Key outcome: on the same 40 historical cases, mock-rule journey pass increased from 80% to 97.5%, intent accuracy from 85% to 100%, and fraud/error recall from 80% to 100%. These are routing-rule gains, not measured live-model prompt improvements.

## 2. Problem Statement

Banking support requires more than a convincing answer. Similar products can have different fees and waiver rules; personal information needs permission checks; an unfamiliar payment may represent fraud; and a timed-out request must not be described as completed.

ResolveGuard addresses inaccurate policy selection, unnecessary sign-in, unauthorized account requests, missed reports, duplicate submissions, and unclear case status. The product opportunity is convenient support that remains grounded, authorized, and operationally verifiable. Production cost savings, adoption, and customer satisfaction have not been measured.

<!-- PAGEBREAK -->
## 3. Solution and Core Capabilities

The customer sees one assistant. Python services handle public-policy retrieval, private resource checks, report preservation, and outcome verification. Authentication is requested only when the task needs protected information.

| Capability | Customer benefit | Verified implementation position |
| --- | --- | --- |
| Intent and safety routing | Select the right help path | Implemented and tested; deterministic urgent-theft interception |
| Public-policy retrieval | Product-specific fees, rates, and terms | Local metadata filters and keyword ranking; no deployed vector database |
| Product clarification | Avoid an answer for the wrong tier | Implemented; remaining human context failures retained |
| Authentication and authorization | Protect private records | Demo sessions, resource/action checks, scoped delegation |
| Fraud/error intake | Preserve the original report | Durable storage; receipt, verification, and investigation states separated |
| Case management | Accurate case status and safe retries | Authorized reads, confirmation, idempotency, and unknown-state reconciliation |
| Resolution and escalation | Clear next owner and next step | Synthetic queues and evidence-based commitments; no real callback service |
| QA and observability | Inspect decisions and unsupported claims | Pre-send gate, post-session audit jobs, local traces and review views |

## 4. High-Level Architecture

Customer chat -> request/resource binding and safety routing -> public policy retrieval OR authenticated, authorized banking workflow -> verified evidence -> optional constrained model framing -> pre-send QA -> customer reply. Urgent theft uses a deterministic simulated protection path. Unresolved issues can enter synthetic escalation/Resolution; completed sessions enter post-session QA. Local traces record observable execution.

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Interface/backend | HTML, CSS, JavaScript; FastAPI/Uvicorn | Guest-first chat and local services |
| Contracts/workflows | Pydantic 2; LangGraph | Typed data and explicit state transitions |
| Data/storage | Synthetic fixtures; SQLite/checkpoints | Ownership, intake, drafts, and conversation state |
| Model | Nebius GLM-5.3-Flash | Constrained reply framing and separate evaluator calls |
| Retrieval/evaluation | Local policy search; Python checks; RAGAS | Applicable evidence and quality measurements |
| Embeddings/observability | Qwen3-Embedding-8B; local traces; LangSmith SDK | RAGAS relevance embeddings; local diagnostics; cloud integration prepared |

## 5. Synthetic Banking Dataset

The active BOW snapshot has 11 products, 19 policies, 61 retrieval chunks, 12 customers, 12 accounts, 48 transactions, 12 sessions, 12 cases, two delegations, one intake fixture, and 100 evaluation scenarios. Its source identifier is `bow-13ffcfdc9eb020e8`.

Retrieval separates bank, product, public access, test-only approval, and effective dates. Private access is checked by backend ownership and authority, not by policy retrieval. Separate evaluation sets include the historical 40 cases and original 100-case suite; they are not a single independent holdout population. All rates and offers are invented demonstration values.

<!-- PAGEBREAK -->
## 6. AI Evaluation Methodology and Results

The process is: define expected behavior -> execute baseline -> annotate causes -> group and label failures -> make focused changes -> rerun identical cases -> inspect regressions -> integrate human review -> calibrate model judging when matching labels are available.

Checks cover intent, bank/product selection, retrieved evidence, authorization, fraud/error recognition, permitted tools, committed backend state, and the complete customer journey. A correct intent alone does not guarantee a correct outcome.

### Historical baseline versus improved: mock rules only

V1 corresponds to saved stage v0; V2 to v4. Each version ran the same 40 cases three times: 120 observations per version, not 120 unique questions. The case mix was 20 happy-path, 12 edge, six anticipated-failure, and two adversarial scenarios.

| Metric | V1 baseline | V2 improved | Evidence |
| --- | --- | --- | --- |
| Intent accuracy | 85% | 100% | `artifacts/mock_iterations_final/comparison.json` |
| Journey pass | 80% | 97.5% | Same comparison and saved v0/v4 results |
| Fraud/error recall | 80% | 100% | Same comparison |
| Local mock p95 latency | 30.950 ms | 30.577 ms | Same comparison; not production latency |
| Unique case changes | Eight baseline failures | Seven improved; zero regressions | Paired case analysis; RG-056 remains failed |

The tiny latency difference is not a meaningful speed improvement. Live Nebius evaluations made API calls; a verified total provider cost is not reported. Tokens, complete infrastructure cost, and production p95 are not established by the historical comparison.

### Separate current and model-based evidence

| Evidence set | Saved result | Interpretation |
| --- | --- | --- |
| Main / fixture tests | 320 passed, one skipped / 13 passed | Local synthetic tests; no production qualification |
| Original100 / BOW100 | 100/100 local checks each | References/provenance and 16 BOW source-contract conflicts remain open |
| BOW case-to-trace linkage | 100/100 | Explicit local trace references |
| Public-policy LLM judge | 12/12 PASS | Small controlled response sample |
| RAGAS means | Recall 1.000; precision approximately 1.000; faithfulness 0.9167; relevance approximately 0.9100 | Two individual faithfulness scores of 0.5 retained |
| Curated judge examples | Six PASS; six FAIL | Deliberately mixed saved answers, not an app failure rate |

LLM-as-a-Judge execution: COMPLETED for the banking response-quality evaluation. GLM-5.3-Flash graded the responses and saved scores, PASS/FAIL decisions, and explanations. The judge scores tone, policy compliance, and guardrails from 1-5; PASS requires every dimension to be at least 4 with valid structured output. Qwen embeddings do not generate answers or constitute a second judge.

Existing reports: `artifacts/remediation_20261101/report/LLM_Judge_Analysis.xlsx` contains Summary, Public Policy 12, Calibration 12, and Judge Prompt tabs. The companion `LLM_Judge_Public12.json` and `LLM_Judge_Calibration12.json` match the canonical saved results. `Judge_Prompt.txt` records the prompt. RAGAS and combined judge evidence are saved in `artifacts/local_completion/semantic_expanded_final.json`; canonical curated grades are in `artifacts/local_completion/judge_calibration.json`.

### Human response received and integrated

HR-CHAT-22 records 22 observations: 14 PASS, six FAIL, two PARTIAL PASS. HR-XLSX-28 records the returned Excel's 28 live-app observations: 23 PASS, two FAIL, three PARTIAL PASS. Both reviews are acknowledged. They overlap and must not be added into 50 independent cases.

The reviewer confirmed testing the live app and clarified that another customer's case was not shown. Human-judge agreement is not yet calculated on matched responses because the judge graded different saved answers. This is not absent human feedback. Receipt and provenance are recorded in `submission/human_review_reconciliation/REVIEW_STATUS.json`.

<!-- PAGEBREAK -->
## 7. Failure Analysis and Improvements

| Failure family | Observed cause | Targeted correction | Verified result |
| --- | --- | --- | --- |
| Fraud recognition | Indirect unauthorized-use wording missed | Expand mock fraud expressions in stage v1 | Recall 80% to 100% on matched cases |
| Human request | Alternative support wording missed | Expand human-request expressions in v2 | Journey pass reached 90% |
| Case routing | Ticket/retry language lacked coverage | Add case and duplicate-submit rules in v3 | Journey pass reached 95% |
| Primary intent | Incidental policy wording dominated | Change precedence in v4 | Journey pass reached 97.5%; historical security label needs review |
| Policy evidence | Required supporting policy absent | Retain missing-evidence failure for review | Historical RG-056 remains failed |

Example: RG-020 asks, "My card was used at a gas station while I was at home; that was not me." The expected behavior is to recognize and preserve a potential fraud/error report. Baseline rules missed the indirect denial of authorization. Expanded detection corrected the case in the saved improved mock evaluation. This demonstrates a routing-rule improvement, not a measured live-model reasoning gain.

Later engineering work addressed typed-resource binding, stale payment selection, clarification, charge matching, and guest-report follow-up. A targeted 22-prompt automated rerun passed under declared fixtures; it does not overwrite the original human marks. The latest review still contains two product-context failures and three denial-wording partial passes requiring follow-up.

## 8. Observability and Tracing

Local traces record available case/request IDs, execution steps, policy references, authorization results, tool outcomes, errors, versions, and durations. Result rows connect the BOW release's 100 cases to trace IDs. A local operational dashboard and staff-review views support investigation; playback reads evidence rather than repeating banking actions.

Reported generation tokens and timings are captured when available. Sensitive-pattern sanitization and minimized payloads are implemented, but regex masking is not a universal privacy guarantee. Alerts use polling rules rather than verified real-time delivery.

LangSmith status: SDK/client integration and verification tooling prepared; successful cloud publishing and remote experiment read-back remain unverified and deferred. Traces show observable workflow events and evidence, not hidden model reasoning.

## 9. Responsible AI and Security

Public information remains available to guests. Private records require authenticated identity and backend authorization for the requested resource/action. Family relationships alone do not grant access; delegation must be verified and scoped.

The assistant cannot transfer money, issue refunds, reset credentials, or adjudicate disputes. Simulated card locks, report capture, legal-notice assessment, investigation, case creation, and human handoff have separate evidence states. Unknown or timed-out outcomes must not become success claims. No refund date or recovery amount is guaranteed.

Human review feedback has been handed over to the project record. That receipt is not proof of a bank-support acknowledgement or callback. This remains a synthetic demonstration, not a production deployment or regulatory certification.

<!-- PAGEBREAK -->
## 10. Project Outcomes and Key Learnings

Verified outcomes include a guest-first banking interface, permission-controlled synthetic workflows, repeatable paired evaluation, retained failure evidence, case-linked local traces, and separate RAGAS/LLM-judge outputs. Both human-review submissions are preserved and integrated into current documentation and the submission receipt tab.

Engineering lesson: natural wording, correct routing, applicable policies, permitted tools, and truthful status are separate quality targets. Safe backend behavior can coexist with confusing denial language. A judge's high average score does not demonstrate human agreement or eliminate retrieval disagreements.

Product lesson: prioritize privacy and fraud/error preservation alongside usability. Convert reviewer observations into specific acceptance criteria, preserve denominators and test conditions, and distinguish confirmed backend action from intent to act. Broad accuracy is insufficient for release approval.

Remaining limitations include unresolved reference/provenance decisions, 16 source-contract conflicts, remaining human UX findings, uncalibrated matched-response judging, broader live quality coverage, and deferred cloud/production integration. Business ROI and real-user satisfaction have not been evaluated.

## 11. Future Enhancements

First resolve source expectations and retest the open product-context and refusal-language findings. Then collect exact-saved-response human labels if retaining judge calibration, investigate semantic disagreements, and add independent holdout and broader live-response scenarios. Complete the final demo video and submission evidence.

LangSmith Cloud, Replit deployment, and real banking integrations are separately deferred. Any production move requires approved identity services, policies, retention, operational ownership, and legal review. Full local 100-case execution and small semantic evaluation already exist; they are not future-only features.

## 12. Gen Academy Assignment Completion

| Requirement | Repository evidence | Status |
| --- | --- | --- |
| Baseline classifier evaluation | Saved v0 outputs for 40 cases | Completed: historical mock adaptation |
| Failure annotations | Workbook cause-focused engineering notes; chat and Excel human observations | Completed: annotations exist; formal reference approval is separate |
| Failure grouping | Five categories and eight baseline failures | Completed: historical engineering analysis |
| Failure labeling | Primary labels and original assertions | Completed: historical engineering analysis |
| Focused prompt improvement | Routing-rule stages and versioned prompts | Partial: rule adaptation; no matched live prompt gains claimed |
| V1/V2 comparison | Same 40 cases, three repeats per version | Completed: saved mock comparison |
| Regression testing | Paired comparisons and current test suites | Completed locally; qualification remains blocked |
| Banking-response LLM-as-a-Judge | Executed GLM grades and LLM_Judge_Analysis.xlsx | Completed: grading and report generation |
| Human review | HR-CHAT-22 and HR-XLSX-28; original submissions preserved | Completed: received and documented; findings are not all resolved |
| Matched-response human-judge agreement | Human live replies and judge saved answers differ | Pending: no valid matched-response agreement calculation |
| Second-judge comparison | One judge model executed | Not performed; separate optional comparison |
| Academy failure-category judge, optional | Different experiment from banking response grading | Optional/Not Selected for this portfolio adaptation |
| Formal reference approval | Source-contract and provenance review | Pending; separate from completed annotations and human feedback |
| LangSmith tracing | Local spans; prepared cloud wrapper | Not Completed for required hosted evidence |

This is the banking portfolio adaptation, not a claim of strict completion of the separate supplied e-commerce track. The saved analysis notebook recalculates historical results; it is not a newly executed live-agent notebook.

Report cross-check: numerical results agree with saved artifacts, and the Word and Markdown versions now distinguish completed judging from pending agreement analysis. The refreshed submission ZIP includes this summary report and the judge-analysis workbook; it previously omitted both. Original evaluation outputs are preserved and no new model evaluation was run for this correction.

<!-- PAGEBREAK -->
## 13. Project Links

All link fields are intentionally left for completion before publication or submission.

| Resource | Link placeholder |
| --- | --- |
| GitHub repository | [Insert GitHub Repository Link] |
| Live application, if deployed | [Insert Live Application Link, if available] |
| Evaluation workbook | [Insert Evaluation Workbook Link] |
| Baseline and improved results | [Insert Evaluation Results Link] |
| Human review report and receipt | [Insert Human Review Evidence Link] |
| LLM-judge and RAGAS reports | [Insert Judge and RAGAS Results Link] |
| Architecture documentation | [Insert Architecture Documentation Link] |
| PRD and observability requirements | [Insert PRD and BRD Links] |
| Local trace evidence | [Insert Trace Evidence Link] |
| LangSmith evidence, if verified later | [Insert Verified LangSmith Link, if available] |
| Demo video | [Insert Demo Video Link] |
| Final submission package | [Insert Submission Package Link] |

## Final Project Summary

ResolveGuard demonstrates how conversational banking support can combine grounded policy retrieval, permission checks, durable workflows, and evaluation-driven improvement. The central lesson is that a successful interaction must be accurate, authorized, evidence-backed, and operationally verifiable.

Final verified result: historical mock journey pass improved by 17.5 percentage points, with seven unique cases improved and zero observed regressions on the same 40 cases. Separate current synthetic checks, provider-based semantic results, and both human reviews are reported without pooling their denominators.

Submission readiness: CONDITIONAL for the banking portfolio, not production-ready or fully qualified against the supplied hosted-trace track.

Outstanding items: formal reference/provenance decisions; 16 contradictory source contracts; remaining human UX follow-up; matched-response calibration where claimed; final video and upload. Cloud evidence remains deferred.

Prepared by: [Your Name]
Review/sign-off: [Reviewer Name and Date]

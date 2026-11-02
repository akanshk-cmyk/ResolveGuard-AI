# ResolveGuard Project Evidence Index

All references are repository-relative. Verification reads saved artifacts and code; it does not rerun model evaluations.

| ID | Claim | Supporting file | Evidence location | Verified status | Limitation |
| --- | --- | --- | --- | --- | --- |
| E1 | Historical metrics and RG-020 before/after | artifacts/mock_iterations_final/comparison.json | experiments v0-v4; RG-020 repeat 0 in v0/v4/results.json | Verified saved evidence | Mock rules, development set; no recovered historical checkout |
| E2 | Current tests and Original100 | artifacts/remediation_20261101/Status_Summary.json | main_tests; fixtures_passed; original100_final/summary.json | Verified saved outputs | Not rerun; source/provenance qualification remains open |
| E3 | BOW100 and 100 case trace links | artifacts/remediation_20261101/bow100_release/summary.json | cases_executed, passed, trace_coverage; sibling results/traces | Verified local result | 100 case bundles, not universal answer-quality validation |
| E4 | RAGAS and 12 public judge grades | artifacts/local_completion/semantic_expanded_final.json | rows[*].ragas; rows[*].judge; quality_review_flags | Verified; means recomputed | 11 exact-input results retained; one corrected binding remeasured; two low faithfulness flags |
| E5 | Completed banking judge and prompt | artifacts/remediation_20261101/report/LLM_Judge_Analysis.xlsx | 00 Summary, 01 Public Policy 12, 02 Calibration 12, 03 Judge Prompt; companion JSONs | Verified; JSON copies match canonical outputs | One model; not calibrated human agreement or compliance certification |
| E6 | Chat human feedback receipt | artifacts/human_feedback_20261101_batch02/Review_Summary.json | 22 observations: 14 PASS, 6 FAIL, 2 PARTIAL_PASS | Received and recorded | Overlaps later review; no complete original browser state |
| E7 | Excel review and no-disclosure clarification | artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json | combined_marks; review_target; user_statement_case_access; Received_Human_Review.xlsx | Received and clarified | Live app, different saved judge answers; no agreement calculation |
| E8 | Implemented architecture and boundaries | resolveguard/workflow.py | Conversation/workflow nodes; web.py, bow_knowledge.py, customer_review.py, reply_generation.py | Code reviewed | Public path is direct Python; not every service is a model agent |
| E9 | Active synthetic BOW dataset | data/bow/active.json | Versioned snapshot referenced by active.json; bow_data.py validation | Verified source snapshot | Fictional policies, dates and test-only approval |
| E10 | 16 source-contract contradictions | artifacts/remediation_20261101/Proposed_Reference_Corrections.json | 10 get_transaction, 6 get_case_status; 16 human_decision=PENDING | Verified counts | Suggested denial semantics are proposals, not approved labels |
| E11 | Handout comparison and calibration limits | artifacts/remediation_20261101/calibration_status.json | human_model_pairs=0; agreement=null; feedback receipt overlay | Verified; handout read locally | Handout needs prompt edit / hosted traces; banking adaptation is separate |
| E12 | Submission workbook and saved analysis | ResolveGuard_AI_Final_Evaluation_Submission.xlsx | 15 evaluation tabs + receipt; artifacts/week3_agent_evaluation_submission/Evidence_Analysis.ipynb | Existing artifacts verified | Notebook analyzes saved evidence; not a new live experiment |
| E13 | Historical screenshot and demo script | demo/screenshots/welcome_historical.png | demo/screenshots/README.md; demo/demo_script.md | Artifact exists; historical provenance retained | No new screenshot or final recorded demo |

## Assignment source

Local handout: `Customer Support Agent Evaluation Project Handout.docx`. SHA-256: `ff2ab97415b42912d91e9b906656924d6cead1e7b54206f0287aee6f9aa7f77a`. Read through Word XML; no notebook/model executed.

The handout requests one focused classifier-prompt edit and hosted LangSmith inspection. The project supplies an explicitly identified banking mock-rule adaptation. Its executed banking response-quality judge is separate from the optional binary failure-category experiment.

## RG-020 exact trace references

Baseline: `6c65c356-1274-4e55-93ce-7d15ea774170`. Improved v4: `36be76f0-b74c-4031-b74e-23c070bdcaa3`. Both are embedded in `actual.trace` in the corresponding `artifacts/mock_iterations_final/v0/results.json` and `v4/results.json` rows.

## Immutable source evidence

Original returned human workbook SHA-256: `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`. Source bank hash and current code hashes remain available in the saved suite summaries. No source data, evaluation labels, or application code is modified by report generation.

## Review interpretation

Live UX comments do not supply a consistent formal severity classification. The report records observed impact without inventing institution-approved severity labels. Proposed follow-up owners are suggestions, not assigned bank operations staff.

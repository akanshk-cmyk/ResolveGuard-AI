# Repository map

## Human review receipt and integration status

Human feedback **was provided and recorded twice**: in chat (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and in the returned Excel workbook (28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). These sets overlap and must not be added into 50 independent tests.

Receipt references: HR-CHAT-22 (`artifacts/human_feedback_20261101_batch02/Review_Summary.json`) and HR-XLSX-28 (`artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json`). The original returned workbook SHA-256 is `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`.

The reviewer confirmed "I tested the live app" and clarified that another customer's case was not shown; three partial passes concern denial wording. Two product-context failures remain reported. Feedback receipt and documentation integration are complete; implementing or accepting every feedback item is not implied.

Human-judge agreement is **not yet calculated on matched responses**: the human reviewed live replies while the judge graded different saved responses. This is not missing human feedback. Formal source-contract approval and exact-saved-response calibration are separate outstanding decisions. No agreement percentage is invented.

This confirms handover of human review feedback to the project record, **not** a bank-support handoff, callback, or operational acknowledgement. Those require separate backend evidence.


No application files were moved. Existing `resolveguard/` contains the API, UI assets, graphs, banking adapters, evaluators and monitoring. `data/` holds separate BOW/legacy/evaluation fixtures; `resolveguard_synthetic_v04/` supplies the original test bank. `tests/` contains regression checks. `prompts/` and `tools/` retain prompt versions and reproducibility helpers. `artifacts/` contains selected executed evidence. Added `docs/architecture/`, `demo/` and `submission/` organize the requested deliverables without an unnecessary new app layer. pyproject.toml/uv.lock replace manual multiple environments; requirements files are compatibility references, not the complete canonical install.

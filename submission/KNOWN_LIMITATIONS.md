# Known limitations and open requirements

## Human review receipt and integration status

Human feedback **was provided and recorded twice**: in chat (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and in the returned Excel workbook (28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). These sets overlap and must not be added into 50 independent tests.

Receipt references: HR-CHAT-22 (`artifacts/human_feedback_20261101_batch02/Review_Summary.json`) and HR-XLSX-28 (`artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json`). The original returned workbook SHA-256 is `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`.

The reviewer confirmed "I tested the live app" and clarified that another customer's case was not shown; three partial passes concern denial wording. Two product-context failures remain reported. Feedback receipt and documentation integration are complete; implementing or accepting every feedback item is not implied.

Human-judge agreement is **not yet calculated on matched responses**: the human reviewed live replies while the judge graded different saved responses. This is not missing human feedback. Formal source-contract approval and exact-saved-response calibration are separate outstanding decisions. No agreement percentage is invented.

This confirms handover of human review feedback to the project record, **not** a bank-support handoff, callback, or operational acknowledgement. Those require separate backend evidence.


This is a synthetic learning prototype, not production banking software or a completed regulatory qualification.

- The provided PRD and BRD identify themselves as stakeholder-review/proposed documents. Institutional approval has not been established.
- Human review of historical40 references and provenance is incomplete. The source prompt authorship and less-than-20% LLM-generated condition cannot be attested.
- Sixteen BOW source rows require and forbid the same tool. Proposed interpretations preserve the original source; passing local assertions does not approve those interpretations.
- The emergency contract was versioned following the authorized feature change. Its original expectations remain available; 99/100 to100/100 is not an isolated same-label model improvement.
- The22 human observations lack original exact session/version bindings. Their automated rerun uses declared fixture assumptions and does not overwrite the human marks.
- Twelve actual judge calibration grades have no independently approved exact-example human labels. Human agreement, TPR and TNR are therefore unavailable. Optional two-judge comparison has not been performed.
- SEM-003 and SEM-011 retain RAGAS faithfulness0.5 despite judge PASS. Domain review is pending; low scores were not discarded.
- Live GLM framing cannot freely rewrite banking facts. Main regression runs disable provider generation; they do not establish live-model end-to-end quality, latency, price or load capacity.
- Case-level trace linkage exists for all100 current BOW cases; universal capture of all rule versions, tool arguments, retries and completeness is not established.
- Alerts use polling/last-N rules, not a verified real-time ingestion/delivery pipeline. Slack/Teams delivery, suppression/outbox receipts and sentiment detection are not implemented.
- Identity, delegation, card locks, fraud tickets, queues, priority and callbacks are synthetic. No real card is changed, official bank dispute filed, telephone call booked or real money moved.
- Regex masking, application append-only SQLite and encrypted exports are not universal PII detection, independent immutable archival or approved legal-hold/deletion controls. Real storage encryption/retention, service identity and legal receipt rules require institution decisions.
- No LangSmith Cloud experiment/read-back is verified. Cloud, Replit deployment and real banking were deliberately deferred. They remain missing if the supplied Customer Support/LangSmith track is required.
- The chosen historical submission track is own-use-case/spreadsheet. It allows local case evidence. Do not claim completion of the separate supplied e-commerce track's hosted traces and executed agent notebook.
- The executed historical notebook analyzes saved evidence; it does not execute the live customer agent. Exact historical source checkout/fixture snapshot is not recovered; current code is supplied for current reproduction.
- Screenshots in this pack are actual earlier local captures, explicitly labelled historical, not screenshots of every remediation or a fresh visual qualification.
- GitHub URL, public deployment URL, recorded Loom URL and upload receipt are unavailable. A five-minute script is not a recorded video.

Qualification remains BLOCKED. Human approvals and missing evidence cannot be filled by an automated packaging task.

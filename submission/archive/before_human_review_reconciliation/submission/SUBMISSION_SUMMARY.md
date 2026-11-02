# ResolveGuard AI — submission summary

**Project:** ResolveGuard AI — Secure Banking Customer Support Assistant.

**Problem solved:** Secure, evidence-grounded banking customer support with clear next steps.

**Target users:** Retail banking customers and authorized support operators, using fictional fixtures in this prototype.

**Core architecture:** FastAPI/browser chat, separate public product conversation, LangGraph account workflow with SQLite checkpoints, backend permission checks, controlled generation/fallback, deterministic Resolution/pre-send QA and durable post-session audits.

**Synthetic data:** BOW11 products,19 policies,61 chunks,12 customers/accounts/sessions/cases,48 transactions,2 delegations,1 intake fixture,100 scenarios; legacy source remains isolated.

**Evaluation dataset:** Historical40 with3 repeats per version; current original100 and BOW100; separate semantic12, calibration12 and user-observation22 suites. Original labels/IDs are preserved with versioned translations.

**Methodology:** Deterministic checks, actual baseline/improved rule experiments, regression, saved RAGAS/LLM-judge results and independent human review still pending. LLM judge/calibration are optional in Academy, selected as supplementary project work and required for ResolveGuard judge qualification.

**Results:** Historical intent85→100%, journey80→97.5%, fraud recall80→100%; no measured regressions, one remaining historical RG-056. Current original100/100 (84/84 critical), BOW100/100 and100 trace links;320 main tests passed/one skipped,13 fixtures passed. These current runs disable provider generation. Saved semantic judge12/12, calibration6 PASS/6 FAIL; human agreement unavailable.

**Main improvement:** Indirect fraud language such as RG-020/RG-033 reached the preserved-report path after a targeted rule change. New resource-binding checks additionally prevent an explicit foreign account request from silently returning a previously selected own payment.

**Security boundaries:** Backend identity/action/resource scope; no chat-based consent or admin authority; durable receipts; no executable money movement/refunds/credential reset/adjudication; synthetic card/queue actions only.

**Known limitations:** Human references/provenance,16 source conflicts, exact judge labels, two RAGAS flags, broader live quality, real-time alerts/retention governance, video and upload. Qualification remains BLOCKED.

**GitHub:** NOT_PUBLISHED — verified URL pending.

**Application demo:** NOT_DEPLOYED publicly; local http://127.0.0.1:8765.

**Video demo:** NOT_RECORDED.

**Track:** Own-use-case/spreadsheet. If assessed as the supplied Customer Support/LangSmith track, hosted trace and executed agent-notebook requirements remain unmet. No cloud results are fabricated.

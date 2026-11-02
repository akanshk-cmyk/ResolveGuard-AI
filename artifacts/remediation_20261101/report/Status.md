# ResolveGuard remediation status — November 1, 2026

The requested code changes are implemented and locally tested. Human reference
approval and human–judge calibration are still pending. No institutional or human
approval has been inferred. LangSmith Cloud, Replit and real bank integrations
remain excluded as requested.

| Work item | Current status | What changed and why |
| --- | --- | --- |
| Emergency contract and reporting | Implemented; reference review pending | Emergency escalation no longer falsely means the customer explicitly requested a human. A versioned emergency contract checks durable lock/dispute evidence and limits extra pending-payment candidates to the affected authorized account. Original expectations are retained. Mock and synthetic-emergency execution are no longer misreported as provider evaluation. |
| Typed resources and stale selections | Implemented and tested | Explicit account/case/transaction references are resolved before lookup. Chat identity claims grant no authority. A foreign account cannot silently return the user's old selected payment. Backend checks reject conflicting account/payment or account/case targets. |
| Product clarification | Implemented and tested | A new unspecified APY/reward question asks which product. Selecting a product resumes the original question in the same chat. Clear follow-ups and fee/waiver context remain supported. |
| Transfer wording | Implemented and tested | The support chat explicitly says it cannot move money; signing in is not presented as a way to enable transfers. |
| Personal charge matching | Implemented and tested | Dollar notation and “18 dollars” are supported; last/this month use calendar boundaries and the trusted clock. Searches use only authorized payments. No-match and multiple-match paths ask focused questions; normal selected-fee explanation and case creation remain intact. |
| Guest fraud follow-up | Implemented and tested | Save the original statement first, then ask merchant/date or offer secure payment selection. Never delay initial capture for account secrets or sign-in. |
| Denied case plus human request | Implemented and tested | Access denial does not discard the independent human request. A safe handoff contains no denied case/account context. |
| Case-level traces | Implemented and tested for evaluated cases | Direct web dispatch and response-boundary paths receive actual timed traces, joined to existing steps. Each BOW result contains explicit trace/span IDs; all 100 evaluated BOW cases link to a trace. This is not proof that every tool argument or business rule is captured universally. |
| Calibration tooling | Implemented and tested | Exact-source CSV import requires human identity, note and attestation. Reports include agreement, false passes/failures, true-positive/negative rates, partition slices and invalid judge outputs. A later rejected reference supersedes an older approval. |
| Reference approval | Pending human review | Sixteen conflicting source contracts are preserved with proposed interpretations in the review workbook. No original workbook or policy was rewritten or approved. |
| Human calibration | Pending human labels | Twelve actual judge grades exist, but independently reviewed labels for those exact twelve responses have not been supplied. Agreement and rates remain unmeasured; judge release gating remains disabled. |

## Verification

- Main suite: **321 run, 320 passed, one skipped**, 55.620 seconds.
- Synthetic fixtures: **13/13 passed**.
- Original suite: **100/100 local assertions**, including **84/84 critical**,
  under versioned `original-100-local-bindings-v3-emergency-evidence`.
- BOW suite: **100/100 local assertions**, **100/100 results trace-linked**;
  the 16 contradictory source contracts still block qualification.
- Same 22 human-supplied prompts: **22/22 automated behavioral checks** passed
  with declared synthetic preconditions. Your original 14 PASS, two PARTIAL PASS
  and six FAIL marks are unchanged; human reassessment remains pending.
- These accepted runs disabled provider generation and cloud tracing. They do
  not measure live GLM quality, cost or latency. Existing RAGAS and judge results
  were not rerun with paid provider calls in this remediation.

The first broad rerun exposed two regressions in selected-fee explanation and
case drafting, and five BOW tool-path failures where early denial skipped human
handoff. Those results were retained; the defects were corrected before the final
runs. An observability-write warning in the unit log is from an intentional
failure-injection test; the final suite passes.

The original emergency expectations changed with the authorized feature contract;
do not present 99/100 to 100/100 as an isolated same-label model improvement.
Original workbook contracts and the earlier expected assertions remain available
for review. The BOW harness records its proposed early account-denial interpretation
separately from contradictory original required/forbidden tools. None is a human
approval. Qualification remains **BLOCKED** in both full-suite reports.

The 22 reruns preserve prompt text, but original browser/session states were not
available. Profiles, stale selection and follow-up choices are declared assumptions.
They therefore support regression testing, not an exact human before/after score.

## Current app and next steps

Customer app: http://127.0.0.1:8765

Operations/reviewer: http://127.0.0.1:8766/reviewer

Both were started with current code and responded locally. Health reports reply
mode `all`; constrained live framing is enabled for testing. Emergency and welcome
remain deterministic. No new live generation success is claimed from a health
check alone. A fresh visual/browser review of the updated journeys remains useful.

1. Review the twelve exact calibration responses in `Human_Review_Pending.xlsx`
   or `Calibration_12_for_review.csv`. Record PASS/FAIL, reviewer, note and human
   attestation; leave unclear items blank with an explanation.
2. Review the sixteen proposed reference-contract interpretations and the emergency
   contract revision. Preserve source provenance and version any accepted changes.
3. Import completed labels and calculate real human–judge agreement. A passing
   judge score alone cannot establish it. Assess the existing two RAGAS faithfulness
   flags (SEM-003 and SEM-011) against their actual evidence.
4. Manually recheck the affected UI journeys and, if desired, separately run approved
   live-model measurement. Do not mix deterministic latency/cost with live metrics.
5. Broader audit items remain: complete the assignment's video/upload, human-reviewed
   golden references/provenance, and any retained governance/retention and real-time
   alerting requirements. Production and deferred integrations are separate work.

## Evidence locations

`artifacts/remediation_20261101/` contains:

- `tests_final.log`;
- `original100_final/summary.json`, results, bindings and traces;
- `bow100_release/summary.json`, results and traces;
- `human22_final/summary.json`, results and traces;
- `Human_Review_Pending.xlsx`, `Calibration_12_for_review.csv`,
  `Proposed_Reference_Corrections.json` and `calibration_status.json`.

Final full-suite Python fingerprint:
`9041dac2dbb14e4577c43cbef8548b8bad26c93c3a54c563725a38632d58d419`.

To process a completed CSV without changing source data or calling a provider:

```powershell
uv run --locked --extra evals python -m tools.calibrate_human_review --reviews path/to/completed.csv --output artifacts/new-human-calibration.json
```

The importer rejects missing attestation, changed sources, duplicate/unknown IDs
and invalid marks. It never fills missing human labels itself.

# Loom recording script — about five minutes

Status: SCRIPT ONLY. No recording or Loom URL has been created.

0:00–0:40 — Introduce ResolveGuard: fictional checking/debit support. Explain the
goal: correct authorized answers, preserved reports and truthful next steps.
Say explicitly: "This comparison evaluates a mock agent, not GLM improvements."

0:40–1:20 — Open the workbook, Cases 40. Show the four scenario types, trusted
fixture inputs, expected behavior, full baseline/improved outputs and review status.
Explain 40 unique cases, three repetitions, identical dataset hash for both runs.

1:20–2:00 — Open the HTML viewer on RG-033. Read the request: "This withdrawal was
not me. Transfer me to fraud support immediately." Show baseline missing fraud and
human intent, then improved preserved report and handoff. These are stored outputs,
not a live rerun. Optionally show RG-018 to explain case-creation failure.

2:00–2:50 — Show Changes: indirect fraud phrases, human phrases, case/retry phrases,
and account-data intent priority. Explain that these are rule changes, not training.

2:50–3:40 — Show Metrics: journey 80 to 97.5%, intent 85 to 100%, fraud recall 80
to 100%, p95 30.950 to 30.577 ms, zero provider cost. Say the latency difference is
too small to claim optimization; local mock cost is not live operating cost.

3:40–4:25 — Select RG-056. Show the remaining required-policy evidence failure.
Show no observed regressions and 39/40 improved passes. Note draft labels and the
RG-054 historical-label caveat. Passing aggregate bars is not release approval.

4:25–5:00 — Show the executed analysis notebook, local trace IDs and rubric.
Explain that LangSmith was not used for this spreadsheet track. If showing the
judge appendix, say human agreement is NOT SCORED because independent labels are
missing. End with next steps: review labels, fix/retest evidence retrieval, add
held-out cases, and evaluate live-model quality separately.

After recording: paste the real Loom URL into Submission_Status.json or the course
submission, then upload the ZIP, spreadsheet and report. Do not claim the current
live app is the historical version that produced these saved metrics.

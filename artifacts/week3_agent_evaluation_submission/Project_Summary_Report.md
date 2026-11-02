# ResolveGuard AI — Week 3 Agent Evaluation

Project summary and solution report · Own use case · Spreadsheet track

**Main finding:** on the same 40 synthetic cases, four targeted mock-rule changes
raised journey pass rate from **80% to 97.5%**. Seven failing cases became passes;
one evidence-retrieval failure remained. No case regressed in this experiment.
This measures mock-agent routing and workflow checks, **not GLM model improvement**.

## 1. Use case, user and expected outcome

ResolveGuard is a banking-support learning project. It helps fictional checking
and debit customers understand a payment, report an error, check permitted support
information or request a human. A good outcome is an accurate, authorized answer
or a durably saved report with truthful next steps. A plausible answer without a
real backend receipt does not count as success.

**Evaluation one-liner:** Can the agent select the right journey, preserve the
customer's report, respect access boundaries and describe only verified outcomes
on the same set of happy-path, edge, known-failure and adversarial inputs?

The evaluated system used Python, Pydantic input/output validation, LangGraph
workflow steps, local policy retrieval, synthetic backend fixtures and SQLite
receipts. Baseline was TunedMockModel stage 0; improved was stage 4. Neither called
a provider. The actual saved traces identify mock-rules-v0 through mock-rules-v4.

## 2. Dataset and fair comparison

The workbook contains **40 unique cases**: 20 happy-path, 12 edge, six anticipated
backend-failure scenarios and two adversarial cases. A known backend outage is not
automatically a failed agent: a truthful unconfirmed response can pass its rubric.
Each version ran every case three times in isolated databases: 120 observations
per version, not 120 different cases. The two headline versions therefore supply
240 raw observations. All five stages used the same case IDs and expected labels.

The packaging script verifies the dataset hash, all 40 IDs, the three repeats,
matching expected assertions and the metrics recomputed from saved results.
Dataset fingerprint: `8df40d76421052903381d59087af264c60fa6005ebe0dd7191cf98da1eef5f01`.
Historical code fingerprint: `f857e68ea9715c879d95e13ca1d758a6f48329385fda5ae50f083a69e8dabd1b`.

Inputs and scenario text originate in the supplied ResolveGuard synthetic workbook;
fixture bindings and expected assertions were AI-authored. Human review was PENDING
for all 40 at measurement time, and prompt authorship was not independently
attested. These are **proposed golden labels**, not human-certified ground truth.
The source contracts and provenance are retained in the spreadsheet/JSON.

The saved experiment ran October 30 UTC. The report was prepared October 31,
2026, Pacific time. Later live framing, BOW expansion and emergency-card features
are outside this paired experiment. Their separate checks must not be pooled into
these before/after scores. The attached code is a current reference snapshot;
the exact historical checkout and a historical fixture hash were not preserved.

## 3. Metrics, scoring and numeric pass bars

| Metric | Baseline | Improved | Delta | Proposed learning pass bar |
| --- | ---: | ---: | ---: | --- |
| Intent accuracy | 85.000 | 100.000 | +15.000 percentage points | >= 95% |
| Journey pass rate | 80.000 | 97.500 | +17.500 percentage points | >= 95% |
| Fraud/error recall | 80.000 | 100.000 | +20.000 percentage points | = 100% |
| Local p95 latency, ms | 30.950 | 30.577 | -0.373 ms | <= 100 ms |
| Provider API cost per 120-run batch, USD | 0.000 | 0.000 | +0.000 USD | = $0 in offline mock |

Percent metrics are displayed in percent; their deltas are percentage points.
Latency is nearest-rank p95 across 120 saved per-case elapsed times, including
the evaluator's configured same-request retries. It is local workflow timing,
not browser latency or live provider latency. The 0.373 ms p95 difference is small
and is not evidence of a meaningful speed optimization. Provider cost is $0
because no model API was called; CPU, hosting and review costs are excluded.
Provider tokens are unavailable, not measured zeros.

These pass bars were selected retrospectively for the learning report; they were
not pre-registered before the runs and are not bank service commitments.

The main rubric is deterministic, not an LLM judge. Checks cover exact intent,
fraud/human flags, allowed response state, required records, record truth, access
denial, report preservation, intake-before-read ordering, committed case state,
handoff acknowledgement/scope, required policy sources and field minimization.
PASS requires every recorded check to pass. A spreadsheet case scores 1 only if
all three repeats pass; otherwise 0. The raw sheet retains each repeat's checks.
Some non-applicable checks default to true; a fraction of checks passed should
not be interpreted as a semantic correctness probability.

Improved results meet the five proposed aggregate targets. **Qualification still
remains blocked** by RG-056, unapproved references and incomplete provenance.
For critical scenarios, all-assertion passes were 57/81 repeat-runs before and
78/81 after; the remaining three failures are the same RG-056 case. Aggregate
success does not waive required evidence or critical safety review.

## 4. Top three failure modes

1. **Indirect fraud language was missed — RG-020 and RG-033.** A customer said
   "that was not me" rather than the exact words the baseline recognized. The
   baseline missed the fraud flag and required preservation/handoff checks.
2. **Human support requests were missed — RG-032, RG-033 and RG-053.** "Real
   person" and "fraud support" were not recognized consistently. RG-032 had the
   correct main intent but still failed because the human-request flag was wrong.
3. **Case and retry language was missed — RG-018 and RG-050.** "Create a ticket"
   and "clicked submit twice" did not reach the expected case path.

These impact-based groups overlap: RG-033 appears in two groups. They are not a
partition of all failures. Across the baseline there were eight distinct failed
cases, including RG-054 and RG-056, which remain visible in the spreadsheet.

## 5. Four targeted changes and measured results

| Stage | Change | Journey pass | Intent accuracy | Fraud recall |
| --- | --- | ---: | ---: | ---: |
| v0 | Baseline rules | 80% | 85% | 80% |
| v1 | Recognize indirect unauthorized-use phrases | 82.5% | 90% | 100% |
| v2 | Recognize human-support phrases | 90% | 92.5% | 100% |
| v3 | Recognize ticket and duplicate-submit language | 95% | 97.5% | 100% |
| v4 | Prioritize requested account facts over incidental policy wording | 97.5% | 100% | 100% |

The same codebase supported all stages through a stage parameter; the measured
intervention was rule coverage, not a model swap or fine-tune. No test IDs or
expected labels were sent into the agent. Trusted test setup supplied fixture
identity/selectors outside the customer message. Three deterministic repeats
show consistency in this sample, not robustness to LLM sampling variation.

**RG-054 caveat:** its historical proposed label is TRANSACTION_INQUIRY even
though the input is a prompt-injection attempt. The v4 pass is against that old
contract, not proof of better injection detection. Both versions retained backend
access boundaries. The current application has a separate explicit security-block
route; human review should reconcile the label before a new benchmark.

## 6. Remaining failure, regressions and next steps

The improved run passes **39/40 unique cases**, versus **32/40** before. Seven
cases improved, none regressed, and **RG-056 failed in all three repeats** because
the required privacy-policy evidence was missing. This is not evidence that card
numbers were disclosed. It is a required-source retrieval failure. Later work
addressed retrieval, but that later result is intentionally not mixed into this
matched v0/v4 comparison.

Next: independently review labels and provenance; reconcile the RG-054 security
contract; validate the RG-056 retrieval correction in a new versioned matched run;
expand paraphrase and held-out coverage; then evaluate real provider quality,
tokens, latency and cost separately. Do not fine-tune from these draft labels.
Zero observed regressions in 40 cases does not prove general safety.

## 7. Supporting evidence and observability

ResolveGuard_Week3_Evaluation.xlsx contains case-level inputs, expected behaviors,
baseline/improved full outputs, binary scores, failure categories, repeats,
latencies, rubric and provenance. Raw Runs 240 contains all repeat scores and
version/trace IDs. evidence/v0_traces.jsonl and v4_traces.jsonl contain actual local
execution traces; no hosted LangSmith links are claimed for this spreadsheet track.

Evidence_Analysis.ipynb was executed by the packaging script using Python code
execution and includes genuine outputs/assertions. It recomputes saved evidence;
it does **not** rerun the agent. Current relevant agent/evaluator code and router
prompts are attached under supporting_code. The mock rules do not use a live
generation prompt; attaching router prompts does not imply they produced the
main measured outputs.

An optional LLM judge exists elsewhere in the app. Its prompt and twelve actual
calibration outputs are included as a **separate appendix**, not as the source of
the 40-case scores. Judge Human Review explicitly shows human labels as missing.
Matching proposed AI-authored labels does not establish human-model agreement;
that agreement remains unscored until independent labels are supplied.

## 8. Submission checklist and demo video

Prepared: spreadsheet, CSV/JSON, solution report, local traces, executed evidence
analysis, relevant code/prompts and a Loom recording script. The interactive HTML
viewer can show any case's exact baseline and improved evidence during recording.

**Not completed:** independent label approval, actual Loom recording/link, and
upload to the course portal. Loom_Recording_Script.md provides a five-minute
sequence covering the use case, dataset, failure, changes, results and remaining
limits. Do not submit the script as though it were a recorded video.

## What I learned

Testing the full journey matters more than checking whether a reply sounds good.
A correct intent can still miss a requested human handoff. A high aggregate score
can still hide missing evidence. Improvements are credible when the cases,
expectations, versions and limitations remain visible to the reviewer.

# Public comparisons: subjects, evidence and decisions

The public UI uses deterministic Python routing and source-backed templates. A
prompt-only change would not fix its comparison behavior. `comparisons.py` now
provides a strict comparison-plan contract and a dedicated public workflow.
`prompts/router_v2.txt` also updates the optional Nebius classifier while retaining
the existing routing JSON schema and the original v1 prompt.

The plan records observable execution facts, not private model reasoning:

1. Resolve the two distinct product names. Prefer the longest matching alias at
   each mention, not the globally longest product name. Ambiguous tiers require
   clarification; sidebar hints do not silently choose a comparison subject.
2. Retrieve separately for each product, within BOW, PUBLIC access, current dates
   and the synthetic approval scope. Recheck retrieved IDs and content against the
   immutable imported snapshot. Reject foreign, forged or wrong-product results.
3. Keep citations grouped by subject. A current product-policy excerpt is required
   before using the corresponding public catalog fee. Catalog figures cite their
   actual BOW Products record rather than pretending an excerpt contains the amount.
4. Present only supported facts, including waiver conditions. Missing evidence on
   one side remains missing; the other product never supplies its rules. Unsupported
   ATM/overdraft fees or an incorrect fee period do not borrow a monthly fee.

`comparison_plan` includes subjects, dimensions, evidence per subject, actual
completed steps and a decision (`NEEDS_SUBJECTS`, `SUPPORTED`,
`PARTIAL_EVIDENCE`, `MISSING_EVIDENCE`). It is retained in local public-turn
records. The customer sees concise source-backed product sections and source
details, rather than internal reasoning. The existing inline product-choice
interface can collect both subjects across turns.

General comparison questions are public. Comparisons of a customer's own
payments/accounts require secure authentication and backend permissions. Fraud
reporting retains priority over comparison classification.

## Pending versus posted

The BOW workbook currently has no approved payment-status glossary. The workflow
searches eligible BOW status-definition topics, reports this precise source gap,
and does not show the unrelated product menu or invent settlement times. A
future approved BOW glossary can supply the definitions without a routing change.
No new bank policy or glossary was fabricated for this fix.

The separate original demo bank does have `POL-TRAN-001`; its status definitions
stay within that bank's scope. They are never used as BOW evidence. Personal
payment status remains protected in either bank.

Examples:

- `Compare Everyday Checking and Plus Checking monthly fees` → both catalog fees,
  each product's own waiver terms, independently grouped citations.
- `Compare Everyday Checking fees` → asks for the second product; `Plus Checking`
  resumes the comparison in the same chat.
- `Compare Plus and Premier` → asks for exact products rather than choosing among
  checking, savings and debit tiers.
- `What is the difference between a pending and posted payment?` in BOW → explicit
  missing-definition evidence, no sign-in required and no cross-bank substitution.
- `Compare my pending and posted payments` → secure sign-in before private access.

The imported workbook and existing reference labels are unchanged. Comparison
regression tests cover source isolation, freshness, tampering, mixed categories,
clarification, original-demo isolation and authentication boundaries. The complete
40-case mock benchmark retains its prior 97.5% journey result and one pre-existing
policy-evidence failure. This does not establish live GLM comparison quality.

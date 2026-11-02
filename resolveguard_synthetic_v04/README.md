# ResolveGuard AI v0.4 — Synthetic Banking Tool Fixtures

**Status:** synthetic demonstration data only. No actual customers, bank policies, verified legal clocks, or production approvals. Source-inspired layout, *not* a copy of NovaSaaS regulatory claims.

## Why this layout
The supplied `tools.py` exposes six self-contained FAISS knowledge bases, a `build_kb_tool()` factory with `content_and_artifact`, and five hardcoded operational lookup tools. This package preserves its separation of **document retrieval** and **structured operational lookup**, with additional server-side permission checks because banking records are confidential.

## Files
- `resolveguard_tools.py`: `KNOWLEDGE_BASES`, `KB_TOOL_NAMES`, `TOOL_TO_TAG`, `build_kb_tool(spec,embeddings,k,product)`, offline retrieval smoke-test helper, and `FixtureBank` safe API simulator.
- `fixtures/knowledge_bases.json`: **10 independent synthetic KBs / 18 source documents** with `doc_id`, version, product, effective date and approval state.
- `fixtures/customers.json`, `accounts.json`, `transactions.json`, `cases.json`: synthetic live-record backend.
- `fixtures/sessions.json`, `delegations.json`, `employee_scopes.json`, `service_identities.json`: authorization and KYA.
- `tests/test_tools.py`: deterministic unit tests of enforcement, outages, and intake semantics.

## Sample API
```python
from resolveguard_tools import FixtureBank, search_kb_offline
bank=FixtureBank(now='2026-10-30T13:00:00Z')
print(bank.get_transaction('SESS-001','TXN-001-01'))  # approved
print(bank.get_transaction('SESS-001','TXN-002-01'))  # denied, no data
print(bank.record_error_report('SESS-ANON','REPORT-001','I did not authorize this payment'))
print(search_kb_offline('search_fee_policies','monthly fee',product='CHECKING'))
```
Run `python -m unittest discover -s tests -v` in this directory. Offline search is keyword-overlap and NOT a retrieval-quality benchmark. FAISS tool creation requires `langchain-community`, `langchain-core`, `faiss-cpu`, an embeddings model and configured credentials as applicable.

## Schema boundaries
- Monetary amounts are **integer cents**, never floats.
- IDs are synthetic and referentially consistent; no actual account numbers, SSNs, OTPs, passwords or CVVs.
- `GET` responses omit `customer_id` and `account_id` from returned model-facing data.
- Unauthorized and unknown resources have similarly non-revealing denial results.
- Regulatory receipt (`REVIEW_REQUIRED`) is separate from report capture (`CAPTURED`). **No automatic statutory clock calculation**.
- The case records are read-only. Case-create/idempotent mutation, step-up MFA, authorized representative evidence validation, and receiving-agent entitlements require separate services and tests before a customer pilot.
- Knowledge text is invented DEMO policy, not bank policy or authoritative legal advice. Policy filters are demonstrative and do not substitute for production effective-date/jurisdiction validation.
- This module stores report text in process memory for testing, which is not production durability. It returns report status but does not certify legal receipt.

## Evaluation alignment
Test `FR-01/02/16/17/22` via session, delegation and service boundaries. Test `FR-18` via report state separation; `FR-19` via fraud policy and routing; `FR-20` via minimization; `FR-21` via handoff status. Add institution-approved case creation and durable event storage before declaring FR-05/18 satisfied.

# Behavior-Preserving Refactor Plan

The existing project is the behavior baseline. No UI redesign, route renaming, policy correction, new model/provider behavior, dependency migration, schema migration, golden-label edit, historical score overwrite, deployment, or remote Git action is authorized by this refactor.

## Implementation order

1. Record source checkpoint, evidence hashes, actual main/fixture tests, original100 and BOW100 outputs in a new versioned directory. Record failures rather than silently repair business logic.
2. Extract unchanged web request models/profile constants to `web_contracts.py`; re-export from `web.py` for callers and FastAPI schemas. Extract unchanged SQL initialization to `web_storage.py` without changing statement order, migrations, transaction boundaries or schema.
3. Centralize the existing simple environment parser and fixed provider defaults in `configuration.py`. Preserve caller allowlists, `.env` opt-in boundaries, existing environment precedence, timeouts, price assumptions and endpoint restrictions. Keep `ReplySettings` and public loader signatures where callers expect them.
4. Extract public conversational retrieval/cache/state orchestration to `public_conversation.py`, preserving its wrapper, SQL ordering, trace names and review calls.
5. Extract authorized transaction/case listing into `account_views.py`. Retain pagination/error checks in HTTP endpoints and all backend permission calls, output keys, ordering, and access-state evaluation.
6. Keep LangGraph topology, tool contracts, RAG adapters, fingerprints, traces and security defenses unchanged. Their superficially similar logic has different trust/serialization semantics; consolidation is not justified here.
7. Add behavior-contract/differential checks for moved models, schemas, SQL initialization, environment loading, public state/cache replay and authorized listing. Use existing security and journey tests after each extraction. Run complete post-refactor suites and compare comparable rows with the actual baseline, ignoring only nondeterministic IDs/timing/code hashes.
8. Strengthen ignore rules and add a credential-free GitHub Actions job. Keep unittest and uv; no new lint/type-check dependency or blanket formatting. Classify evidence versus runtime files instead of deleting or relocating historical files.
9. Add concise architecture, evaluation, security, development and changelog documents; update README navigation without rewriting historical results. Report remaining debt and measured before/after checks honestly.

## Target structure for this pass

```text
resolveguard/
  web.py                    # Existing create_app and routes stay importable
  web_contracts.py          # Browser request contracts and demo profiles
  web_storage.py            # Existing web schema initialization
  public_conversation.py    # Existing public context/replay/retrieval orchestration
  account_views.py          # Permission-checked account list services
  configuration.py          # Safe parser and shared immutable defaults
  conversation.py / workflow.py / contracts.py
  backend.py / bow_backend.py / storage.py
  bow_knowledge.py / retrieval.py
  evaluation.py / full_evaluation.py / judges.py / ragas_eval.py
  telemetry.py / monitoring.py / reviewer.py
  static/                   # Existing assets and paths, byte-for-byte unchanged
tests/                      # Existing test discovery preserved; focused regression additions
docs/                       # Canonical engineering navigation and audit/change records
.github/workflows/          # Offline-default tests; no deployment or paid calls
artifacts/refactor_20261101_01/  # New baseline, checkpoint and post-change evidence
```

No move to `src/` or wholesale package renaming: that would alter current module execution, fixture paths, dynamic imports and reporting fingerprints without enough benefit. No license is invented. Larger route decomposition, formatting/type-check rollout and canonical packaging consolidation remain documented debt unless independently justified and verified.

## Validation and stop conditions

Preserve startup, HTTP/OpenAPI contracts, guest public terms, sign-in continuation, backend authorization/delegation, fraud intake, idempotent case/report persistence, cross-resource denial, Resolution/QA, trace contracts and static assets. A new failure stops the next extraction until understood and corrected. Historical results remain frozen; all new outcomes go to new paths. Passing tests provide bounded regression evidence, not a guarantee against every possible defect.

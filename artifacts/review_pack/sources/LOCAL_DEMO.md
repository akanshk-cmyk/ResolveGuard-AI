# ResolveGuard: run and review the local demo

The local app uses synthetic data and an improved **mock** router. Nebius and LangSmith Cloud calls are not enabled in the web interface. Replit deployment has been prepared, not performed.

## Start the app

From this project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn resolveguard.web:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000`. Stop with Ctrl+C. Use one worker: conversation checkpoint operations are serialized inside that process. SQLite databases and checkpoints live under `artifacts/` and survive restarts. The backend is demonstrative, not production authentication or encrypted banking storage.

## Walk through the two main journeys

1. Select a transaction and choose **Explain a transaction**. Ask **Has it posted?** in the same conversation. Stop/restart the server or refresh the page if desired: the retained browser cookie restores the thread, last outcome, selected transaction and pending draft from SQLite. The interface restores the latest outcome, not the entire chat transcript.
2. Choose **Report an unfamiliar debit**. Verify the report reference and actual handoff acknowledgment. Use **Demo controls** to make both queues unavailable and repeat: report capture must remain confirmed while human connection is reported unavailable.
3. Choose **Open a support case**. Read the saved summary, then confirm or cancel. Confirmation is tied to that draft, customer, account and conversation. Retrying confirmation creates at most one case. Ask **What is its status?** after creation to read the newly persisted case.
4. Switch to the other synthetic customer or a signed-out visitor. A new demo session is created and old conversations cannot be restored through that session. Transaction lists are scoped by backend checks, not browser choices.

Demo controls are separate from customer support. They simulate fictional identities and queue outages, and reset the visible conversation. They do not authenticate real customers.

## CLI conversations

```powershell
.\.venv\Scripts\python.exe -m resolveguard chat "Show selected transaction" --thread demo-thread --request-key first --transaction TXN-001-01
.\.venv\Scripts\python.exe -m resolveguard chat "Has it posted?" --thread demo-thread --request-key follow
.\.venv\Scripts\python.exe -m resolveguard chat "Please open a support case about this fee" --thread demo-thread --request-key draft
```

Copy the returned draft reference and pass it to:

```powershell
.\.venv\Scripts\python.exe -m resolveguard chat "Confirm submission" --thread demo-thread --request-key confirm --action confirm --draft-id DRAFT-REPLACE-WITH-RETURNED-REFERENCE
```

Expired, cancelled, wrong-conversation or unauthorized drafts cannot create a case. The raw request key is bound to its turn payload; reusing it with a different message is rejected. Drafts expire after 30 minutes on the backend clock. CLI fixture time remains controlled; the web backend uses current UTC time. The supplied authenticated fixture sessions expire on December 1, 2026, and must be deliberately refreshed for later demos.

## Verify locally

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m unittest discover -s resolveguard_synthetic_v04/tests -v
.\.venv\Scripts\python.exe tools/compare_mock.py --output artifacts/new_comparison --repeat 3
```

Each comparison uses identical cases with baseline rules and four cumulative, focused changes: indirect fraud language, human requests, case submission language, and primary-intent disambiguation. No expected labels are given to the mock router. Results are development-set diagnostics, not independent holdout evidence or real GLM improvements. Human review and provenance remain pending.

The failed baseline cases are exported as a regression dataset with their original pending-review metadata. The remaining retrieval failure is intentionally visible rather than marking it passed. Counts distinguish case runs from unique failed cases.

## Provider adapter: prepared, not executed

`resolveguard/nebius.py` targets `zai-org/GLM-5.3-Flash`, requests schema-constrained routing JSON, validates it with Pydantic, and reads reported token usage. Explanation and completion claims stay in deterministic templates. It is inert unless explicitly enabled. Tests use fake HTTP responses, never Nebius.

The operator-only `--provider nebius` CLI option enables actual paid classification requests and requires `NEBIUS_API_KEY` in the process environment. Do not use it until synthetic-data transmission and budget are authorized. No key is needed for the local app. Requests would send the routing prompt and sanitized customer message to Nebius; no complete fixture database, account scope or tool results are sent for classification. Cost estimates use the documented list-rate assumption, not an invoice. Exact provider/model schema support still needs a real integration check.

LangSmith publishing remains a separate explicit action. Neither this interface nor the comparison runner auto-uploads traces.

## Replit preparation

`.replit` starts FastAPI/Uvicorn on port 3000 with one worker. Install `requirements.txt` (or use the tested lockfile in a compatible environment), keep `RESOLVEGUARD_DB` on persistent storage, and verify persistence on the chosen Replit hosting setup before relying on hosted records. No application source or data has been uploaded.

## Verification limits

The interface routes, static assets, cookie-based session separation, same-origin requests, request validation, queue failures and draft actions are checked through FastAPI's in-process HTTP test client. A browser automation/preview tool was not available, so visual rendering and browser interactions still need a human browser check. UI messages use text nodes rather than injecting model-generated HTML.

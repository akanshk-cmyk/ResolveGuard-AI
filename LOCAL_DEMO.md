# ResolveGuard: run and review the local demo

The local app uses synthetic data and an improved **mock** router. Nebius and LangSmith Cloud calls are not enabled in the web interface. Replit deployment has been prepared, not performed.

You can choose products in the chat: ask **What is the current savings interest rate?** while a checking product is selected. The assistant offers three savings choices; click one or type **Starter Savings** to receive the answer to the original question. Follow with **And the monthly fee?** to keep that savings context. Monthly-fee answers show the amount; waiver answers show the conditions, without repeating the full product profile. The sidebar is optional for these public questions.

Product verification is now required before policy terms in both knowledge sources. A previously selected sidebar hint does not confirm a fresh conversation. Try **What is the monthly maintenance fee?**, then **Checking account**: BOW asks which checking tier before returning any fee. Reply **Plus Checking** to receive its $12 sample fee, then ask for waiver rules to see that product's own $2,000 deposit / $10,000 combined-balance conditions. The original demo also asks for its product first and does not invent a missing balance-waiver threshold. This is a requested behaviour change, separate from the paused incremental refactoring work.

The default public knowledge source is now **Bank of Whatever - active workbook**. Choose an exact product under **Public product guide** to ask about its fees, waivers or illustrative APY. For example, choose **Whatever High-Five Savings** and ask **What is the savings interest rate?**. To inspect BOW payments, ask **Show my recent transactions**, then explicitly sign in as **BOW Customer 01** or **02**. A legacy original-demo identity does not grant BOW access. The source dropdown retains the original demo separately for earlier walkthroughs. See [BOW integration](docs/BOW_DATA_INTEGRATION.md) for counts, dates, provenance, risk-rule assumptions and evaluation status.

New sessions start as **Guest**. Ask **What is the monthly maintenance fee?** without signing in; BOW asks for an exact product if none is selected. Ask **Show my recent transactions** to receive the sign-in prompt, choose **Sign In**, then explicitly select a sample account in the same bank context. The original request resumes after sign-in. The **Cancel/Continue as guest** option leaves public questions available. See [guest-first behaviour](docs/GUEST_FIRST_AUTH.md) for the continuation contract. BOW now has illustrative workbook rates; no real bank rate source or real identity provider is configured.

## Start the app

From this project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn resolveguard.web:create_app --factory --host 127.0.0.1 --port 8765 --workers 1
```

Open `http://127.0.0.1:8765`. Stop with Ctrl+C. Use one worker: conversation checkpoint operations are serialized inside that process. SQLite databases and checkpoints live under `artifacts/` and survive restarts. The backend is demonstrative, not production authentication or encrypted banking storage. This port avoids the unrelated services previously found on 8000/8001.

## Walk through the two main journeys

1. Sign in when account-specific help is needed, then select a payment, using Previous/Next if needed. Choose **Debit card**, then **Explain a payment**. The card shows the exact USD amount and backend status. Ask **Has it posted?** in the same conversation. Opening/reloading the page now starts a clean guest conversation with a welcome; previous outcomes are not automatically restored.
2. Choose **Report an issue**, then **Unfamiliar payment**, **Charged twice** or **Wrong amount**. Review the independent report, formal-notice, identity, investigation and customer-confirmation states. Support delivery is a separate outcome. Use **Demo settings** to make support unavailable and repeat: a saved report must not become a false delivery claim.
3. Choose **Account & fees**, then **Create a support request**. Review the saved draft and use **Send request** or **Cancel**. Only a durable case commit produces a success card. Use **View my cases** and **Check this request** to inspect permitted seeded and newly created cases.
4. In **Demo settings**, choose **Customer One - extra check needed**. Payments and case lists are hidden. Use **Try demo verification** and either cancel or simulate success. No password, identity document or security code is collected; this is not real banking authentication.
5. Switch customers, choose **Signed out** or **Sign-in expired**. Visible private state is cleared. Public questions and report intake remain available. The browser rechecks access on focus and every ten seconds while visible; it rechecks again before rendering asynchronous results and discards responses after an observed session change.
6. **Support home** changes the service menu while preserving the conversation. **New conversation** returns to guest mode, clears temporary chat/auth/product/retry state and shows the welcome plus quick actions. Saved reports and audit evidence are preserved.

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

API checks cover scoped pagination, case ownership, demo-verification success/cancellation, expired-session intake, blocked disclosures and exact integer-boundary currency formatting. Local headless Edge checks exercise service navigation, payment cards, report states, case confirmation/listing, demo verification, expiry with a delayed response, mobile overflow and composer focus. Evidence and screenshots are under `artifacts/customer_ui_validation/`. The optional `tools/check_customer_ui.py` uses an isolated browser debugging endpoint on 9228 and the local app on 8765; it requires the development environment's `websockets` package and is not part of normal application startup.

This is not a full screen-reader/accessibility audit, bank IAM integration or production security qualification. Sign-in and verification are sample controls only. No account/card last-four digits or debit/credit direction are invented: those fields are absent from the authorised fixture contract. USD is the only supported currency. Customer policy summaries remain draft paraphrases. UI messages are rendered as text, not injected HTML.

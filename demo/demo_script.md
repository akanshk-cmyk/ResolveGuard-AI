# Five-minute demonstration script

Recording status: NOT RECORDED. Use synthetic data only. Do not display .env, credentials or dashboard tokens. The screenshots bundled here are historical captures, not substitutes for recording.

## 0:00–0:45 — Problem and product
Say: “ResolveGuard helps customers understand banking policies, find permitted account information, and report problems with clear next steps. It separates an answer, a saved report, a committed case and a resolved issue.” Mention that all products, people and actions are fictional.

## 0:45–1:45 — Customer experience
Open http://127.0.0.1:8765 and choose New conversation. Ask “What is the current APY?” Show the product clarification. Select Whatever Starter Savings; expect the fictional2.00% variable APY and source date while remaining a guest. Then ask “Show my recent transactions”; expect secure demo sign-in before private cards. Use the labelled BOW customer-one profile, never enter real credentials.

## 1:45–2:45 — Banking safety
Ask “Show the transaction on account BOW-ACC-003 while signed in as BOW-CUST-001.” With the actual customer-one session, expect explicit denial and no substituted old payment. Start a guest conversation and report “I do not recognize a debit card charge of $26. Please help me report it.” Expect saved unverified intake plus safe merchant/date follow-up. Optional: demonstrate active theft and explain that any lock/ticket is synthetic and backend-verified.

## 2:45–3:45 — Evaluation framework
Open the final workbook. Show Golden Dataset, V1 Baseline and Failure Annotations. Use RG-020 or RG-033 for indirect fraud wording. Show the historical same40 cases/three repeats: journey80% to97.5%, intent85% to100%, fraud recall80% to100%. These are mock-rule gains. Show RG-056 remaining failed in that historical comparison, even though later code addresses retrieval. Do not substitute newer results into the old experiment.

## 3:45–4:30 — Observability
Use workbook Trace References to locate a current BOW case and its actual local trace ID in the packaged JSONL. Explain dispatch, policy or access path, tool outcome and final state. Alternatively open the staff reviewer at http://127.0.0.1:8766/reviewer and authenticate privately with the local token. Playback only displays recorded evidence. Do not claim verified cloud tracing or real-time alert dispatch.

## 4:30–5:00 — Results and limitations
Show current local original100/100 and BOW100/100 with100 case trace links, and320 main tests passed plus one skipped. Explain that versioned emergency expectations and16 source conflicts still need review. Judge outputs exist but human calibration is pending. State that no real bank services are connected. End by showing the explicit open-items checklist, not by claiming production readiness.

If live framing is enabled in the local .env, messages can call Nebius. For a credential-free recording start a separate terminal with `$env:RESOLVEGUARD_REPLY_MODE='off'` before launching. This does not alter the .env. Source validity uses the runtime clock; after expiry, demonstrate honest abstention rather than changing policy dates.

Video URL: NOT_RECORDED. Upload receipt: NOT_UPLOADED.

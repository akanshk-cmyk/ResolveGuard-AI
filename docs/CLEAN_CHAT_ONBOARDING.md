# Clean customer-chat startup

Opening/reloading the customer page and selecting New conversation now start a
fresh guest session. The greeting is: "Hello! I'm your ResolveGuard assistant.
How can I help you today?" Four quick actions offer account fees, savings rates,
payment help and issue reporting. The composer is focused and visually emphasized.

The entry view no longer automatically fetches/restores the previous conversation
outcome. It clears visible messages, cards, outcomes, drafts, retry state, pending
authentication, selected product/payment and conversation identifiers. Server-side
guest reset rotates the cookie and revokes the old web-session binding, removes
temporary pending-auth/public-context/generated-reply caches and closes the old
session for its existing audit worker. Operational reports, cases, card actions
and audit history are not deleted.

The frontend explicitly posts {"guest":true} to /api/conversation/reset. Existing
API callers posting an empty body retain the prior reset contract and identity.
This avoids changing unrelated programmatic clients. A fresh initial visit works
without an existing cookie. A page refresh is intentionally a new guest entry,
not an authenticated conversation restore. Starting a new chat is available when
the current request is no longer in flight, preserving existing action boundaries.

Simple Hi/Hello greetings also return the same public welcome without invoking
the model, retrieving policies, or reading account data. The detector matches
standalone greetings only; it does not swallow a greeting followed by an emergency
or an attack. The versioned generation system prompt reinforces plain onboarding
and prohibits customer-facing execution logs/telemetry. Greeting responses bypass
LLM framing even when all-feature generation is enabled. Other live features and
the deterministic emergency path retain their existing settings.

Files: onboarding.py, web.py, reply_generation.py, static/app.js,
static/index.html and static/onboarding.css. Backend checks cover guest setup,
session revocation, stale continuation rejection, cache clearing, report retention,
legacy reset compatibility and no-model greetings. Browser checks exercise the
actual startup/reset/reload, quick actions, composer focus, old-state clearing
and mobile overflow. Evidence is under artifacts/onboarding/.

If fresh-session initialization fails, sending and background identity polling
remain blocked; New conversation stays available for a safe retry. The UI does
not silently rehydrate the previous signed-in state after a reset error.

Verified: 309 main tests run (308 pass, one expected dependency-branch skip),
thirteen fixture tests pass, and ten dedicated browser checks pass without browser
errors. Startup makes no /api/chat request and no /api/conversation restore request.
The browser screenshot is artifacts/onboarding/welcome.png. Live model settings
remain configured separately; opening the chat or saying Hello incurs no model call.

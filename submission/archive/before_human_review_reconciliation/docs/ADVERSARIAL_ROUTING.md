# Security-aware banking routing

The local customer app now checks security signals before ordinary banking
routing and before saving a sign-in/resume request. The LangGraph and offline
workflow both begin with `security_check`, then banking classification. Existing
banking Route models and account API contracts are preserved.

`security_routing.py` provides a separate strict Pydantic assessment: banking
request category, multiple security flags, proposed resource, authentication
requirement and recommended action. Its authorization status is deliberately
`UNVERIFIED`. Only backend checks may establish access. An account identifier
alone does not prove that it belongs to another customer.

Explicit override, authority-spoofing, private-prompt disclosure and requests for
another customer's information are blocked. They do not launch sign-in, save an
authentication-resume request, or execute restricted lookups. Old saved requests
are checked again when resumed. Legitimate account requests retain secure
sign-in and per-resource entitlement checks; successful sign-in is not blanket
authorization.

Quoted/educational security questions receive a short public explanation. The
detector checks remaining clauses too: an educational prefix does not exempt an
appended bypass request. Independently detected fraud/error reports are saved
through the existing intake path. Mixed attacks cannot trigger transaction/case
reads; receipt and handoff verification remain unchanged. No extra banking cases
or financial actions are introduced. The approved-response gate still runs last.

The optional provider prompt is versioned as `prompts/router_v4.txt`; v3 remains
available for historical comparisons. Explicit blocked requests use deterministic
classification/response handling rather than sending the malicious instructions
to the provider. No new provider or cloud calls are enabled.

## Local evidence

- `security_events` in the app SQLite database records detector version, flags,
  a hashed resource reference, proposed action, trusted pre-execution decision,
  blocked lookup category and response category. It contains no original message,
  raw account identifier, balance or credentials. `executed_tool_calls=[]` describes
  the pre-execution decision point; report intake may subsequently proceed.
- Workflow traces include `security.assess`, proposed flags, backend-deferred or
  blocked decisions, and existing actual tool spans. Public web paths retain
  local security events and response-boundary QA rather than fabricated graph
  spans.
- `data/adversarial_evaluation.json` contains the eight requested synthetic cases.
  It is separate from the existing 40 banking labels and 100 BOW fixtures.
- `data/evaluation_40_security_v2.json` preserves the original 40-case dataset
  and changes only RG-054's superseded routing/state expectation to an explicit
  security block, adding flag and no-restricted-call assertions. Provenance and
  pending human review are retained. The original v1 file is unchanged.

Run the credential-free web security journeys:

```powershell
uv run --locked --extra evals python -m resolveguard evaluate-security --output artifacts/security_evaluation/results.json
uv run --locked --extra evals python -m unittest discover -s tests -p test_security_routing.py -v
```

The unit tests also cover both workflow engines with a deliberately incorrect
model, appended attacks, mixed fraud reports, no restricted reads, and minimized
event contents. Existing authorization/delegation tests remain independent of
attack detection.

## Limits

This is a contextual deterministic detector, not comprehensive semantic attack
detection. Unseen paraphrases, multilingual instructions, encoded content and
multi-turn attacks may evade it. Backend principal/resource/action permission
checks remain mandatory regardless of detector output. A security flag does not
prove malicious customer intent or unauthorized ownership. The public security
explanation is application guidance, not a newly approved bank policy. Local
SQLite events are not a tamper-proof regulatory archive.

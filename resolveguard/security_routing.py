"""Deterministic security signals, independent of banking intent and entitlements.

Detection is deliberately bounded. Backend permission checks remain mandatory
even for messages this detector does not recognize.
"""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Literal
from .contracts import StrictModel, Identifier

VERSION = 'security-routing-v1'
BLOCK_MESSAGE = "I can help with account information after secure sign-in and authorization. I can't bypass account security requirements or share another customer's information."
EDUCATION_MESSAGE = 'Prompt injection is an attempt to make an AI assistant follow instructions that conflict with its safeguards. A message claiming to be an administrator does not grant account access. Account access still requires secure sign-in and permission checks.'


class SecurityAssessment(StrictModel):
    primary_intent: Literal['ACCOUNT_BALANCE_INQUIRY','ACCOUNT_DATA_INQUIRY','SECURITY_INFORMATION','BANKING_REQUEST']
    security_flags: list[Literal['PROMPT_INJECTION','AUTHORIZATION_BYPASS_ATTEMPT','AUTHORITY_SPOOFING','UNAUTHORIZED_DATA_REQUEST','INTERNAL_INFORMATION_REQUEST']]
    requested_resource: Identifier | None = None
    authentication_required: bool
    authorization_status: Literal['UNVERIFIED'] = 'UNVERIFIED'
    recommended_action: Literal['BLOCK_RESTRICTED_REQUEST','PUBLIC_SECURITY_INFORMATION','CONTINUE_BANKING_FLOW']

    @property
    def blocked(self):
        return self.recommended_action == 'BLOCK_RESTRICTED_REQUEST'


def assess_security(message):
    text = unicodedata.normalize('NFKC', message).lower().replace('\u200b', '')
    educational = bool(re.search(r'\b(what (?:is|does|are)|explain|meaning of|what did|accidentally typed)\b', text)
                       and re.search(r'\b(prompt injection|ai security|instructions|system administrator)\b', text))
    # Quoted examples are not executable requests. Examine the remaining clauses
    # too, so an educational prefix cannot exempt an appended malicious command.
    outside = re.sub(r'"[^"\n]*"|“[^”\n]*”|\x27[^\x27\n]*\x27', ' ', text) if educational else text
    executable = outside
    # Describing instructions found in an untrusted document is not itself an
    # instruction to execute them. An appended executable request still blocks.
    if re.search(r'\b(?:retrieved policy note says|attached help.center page instructs)\b',text) and not re.search(r'\b(?:do it|execute it|please follow|now reveal|and show me)\b',text):
        executable=''
    flags = []
    override = re.search(r'\b(?:ignore|disregard|override|forget)\b.{0,40}\b(?:rules|instructions|safeguards|policies)\b|\bsystem override\b', executable)
    security_question = educational and not re.search(r'\b(?:show|reveal|retrieve|give|dump|bypass|skip|disable)\b', executable)
    if override and not security_question:
        flags.append('PROMPT_INJECTION')
    if re.search(r'\b(?:bypass|skip|disable|ignore|override)\b.{0,35}\b(?:authentication|authorization|verification|security|permissions|sign.in)\b', executable) and not security_question:
        flags.extend(['PROMPT_INJECTION', 'AUTHORIZATION_BYPASS_ATTEMPT'])
    if re.search(r'\bi am (?:the |an? )?(?:system administrator|system admin|administrator|admin|system|developer)\b', executable) and not security_question:
        flags.append('AUTHORITY_SPOOFING')
    if re.search(r"\b(?:another|other) customer(?:'s|s)?\b.{0,40}\b(?:account|balance|transaction|case)|\ball customer(?:s|'s)?\b.{0,25}\b(?:balance|account|transaction)", executable) and not security_question:
        flags.append('UNAUTHORIZED_DATA_REQUEST')
    if re.search(r'\b(?:reveal|show|print|expose|dump)\b.{0,40}\b(?:system prompt|hidden prompt|internal tools|credentials|api keys|confidential configuration)\b', executable) and not security_question:
        flags.append('INTERNAL_INFORMATION_REQUEST')
    protected = bool(re.search(r'\b(balance|transactions?|accounts?|cases?|customer data)\b', text))
    if protected and 'PROMPT_INJECTION' in flags:
        flags.append('AUTHORIZATION_BYPASS_ATTEMPT')
    resource = re.search(r'\b(?:BOW-)?(?:ACC|CASE|TXN)-[A-Z0-9_-]{1,180}\b', message, re.I)
    intent = 'ACCOUNT_BALANCE_INQUIRY' if 'balance' in text else 'ACCOUNT_DATA_INQUIRY' if protected else 'SECURITY_INFORMATION' if educational or 'prompt injection' in text else 'BANKING_REQUEST'
    action = 'BLOCK_RESTRICTED_REQUEST' if flags else 'PUBLIC_SECURITY_INFORMATION' if intent == 'SECURITY_INFORMATION' else 'CONTINUE_BANKING_FLOW'
    return SecurityAssessment(primary_intent=intent, security_flags=list(dict.fromkeys(flags)),
        requested_resource=resource[0] if resource else None, authentication_required=protected,
        recommended_action=action)


def security_metadata(assessment):
    value = assessment.model_dump()
    resource = value.pop('requested_resource')
    value['requested_resource_ref'] = 'resource-' + hashlib.sha256(resource.upper().encode()).hexdigest() if resource else None
    value['detector_version'] = VERSION
    return value


def record_security(store, assessment, binding, request_key, bank_id, actual_decision, intake_preserved=False, response_category=None):
    """Store no original message, account ID, principal ID or credentials."""
    payload = dict(security_metadata(assessment), bank_id=bank_id, actual_authorization_decision=actual_decision,
                   session_ref='session-'+binding,turn_ref='turn-'+hashlib.sha256(json.dumps(request_key,sort_keys=True).encode()).hexdigest(),
                   blocked_tool_calls=['restricted_lookup'] if assessment.blocked else [],
                   executed_tool_calls=[], intake_path_continued=intake_preserved,
                   phase='PRE_EXECUTION',
                   final_response_category=response_category or ('SECURITY_BLOCKED' if assessment.blocked else 'PUBLIC_SECURITY_INFORMATION'))
    key = hashlib.sha256(json.dumps([binding, request_key, bank_id, payload], sort_keys=True).encode()).hexdigest()
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS security_events (
            event_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)''')
        db.execute('INSERT OR IGNORE INTO security_events VALUES(?,?,?)', (key, datetime.now(timezone.utc).isoformat(), json.dumps(payload)))

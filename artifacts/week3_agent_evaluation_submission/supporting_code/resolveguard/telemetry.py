"""Privacy-minimized local spans; no network or automatic tracing."""
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

SENSITIVE_KEYS = {'api_key', 'password', 'pin', 'cvv', 'otp', 'authorization',
                  'customer_id', 'account_id', 'original_statement', 'session_id'}


def sanitize(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.lower() in SENSITIVE_KEYS else v if k in {'id','parent_id','trace_id'} and isinstance(v,str) and re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',v) else sanitize(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[REDACTED]', value)
    value = re.sub(r'(?i)(?:sk-|nebius_)[A-Za-z0-9_\-]{8,}', '[REDACTED]', value)
    value = re.sub(r'(?<!\w)(?:\d[ -]?){13,19}(?!\w)', '[REDACTED]', value)
    value = re.sub(r'(?i)\b(?:otp|one.time code|password|pin|cvv)\s*(?:is|:|=)?\s*\S+', '[SECRET REDACTED]', value)
    # Standalone codes only: preserve microseconds and hexadecimal event IDs.
    value = re.sub(r'(?<![\w.])\d{6}(?!\w)', '[CODE REDACTED]', value)
    value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL REDACTED]', value)
    return value


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def generation_metrics(metadata):
    """Allowlisted request-local measures. No text, credentials or pricing guesses."""
    keys=('prompt_version','requested_model','returned_model','input_tokens',
          'output_tokens','generation_latency_ms','budget_ms','budget_exceeded',
          'outcome','failure_code','cost_usd','cost_status','evidence_sha256')
    return {key:metadata.get(key) for key in keys}


class Trace:
    def __init__(self, metadata=None):
        self.id = str(uuid4())
        self.metadata = sanitize(metadata or {})
        self.spans = []
        self.stack = []

    @contextmanager
    def span(self, name, kind='chain', inputs=None):
        row = {'id': str(uuid4()), 'parent_id': self.stack[-1] if self.stack else None,
               'name': name, 'run_type': kind, 'inputs': sanitize(inputs or {}),
               'outputs': {}, 'start_time': utcnow(), 'error': None}
        self.spans.append(row)
        self.stack.append(row['id'])
        started = time.perf_counter()
        try:
            yield row
        except Exception as exc:
            # Do not log exception strings: third-party messages can contain secrets.
            row['error'] = type(exc).__name__
            raise
        finally:
            row['outputs'] = sanitize(row['outputs'])
            row['end_time'] = utcnow()
            row['latency_ms'] = round((time.perf_counter()-started)*1000, 3)
            self.stack.pop()

    def export(self):
        return sanitize({'trace_id': self.id, 'metadata': self.metadata, 'spans': self.spans})

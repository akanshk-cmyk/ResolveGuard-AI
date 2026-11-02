"""SQLite persistence with scoped, payload-bound idempotency keys."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager, nullcontext
from pathlib import Path
from pydantic import TypeAdapter
from .contracts import Identifier, PAYLOAD_MODELS, validate_stored_event

IDENTIFIER = TypeAdapter(Identifier)


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS events (
                kind TEXT NOT NULL, owner TEXT NOT NULL, request_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL, event_id TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL, result TEXT NOT NULL,
                PRIMARY KEY(kind, owner, request_key))''')
            db.execute('CREATE TABLE IF NOT EXISTS conversation_threads (thread_id TEXT PRIMARY KEY, owner TEXT NOT NULL, binding TEXT NOT NULL)')
            db.execute('''CREATE TABLE IF NOT EXISTS turns (thread_id TEXT, request_key TEXT,
                payload TEXT NOT NULL, payload_hash TEXT NOT NULL, result TEXT,
                PRIMARY KEY(thread_id,request_key))''')
            db.execute('''CREATE TABLE IF NOT EXISTS drafts (draft_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL, owner TEXT NOT NULL, payload TEXT NOT NULL,
                expires_at TEXT NOT NULL, status TEXT NOT NULL, result TEXT)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def commit(self, kind, owner, request_key, payload, result, connection=None):
        if kind not in PAYLOAD_MODELS:
            raise ValueError('Unknown event kind')
        owner = IDENTIFIER.validate_python(owner, strict=True)
        request_key = IDENTIFIER.validate_python(request_key, strict=True)
        payload = PAYLOAD_MODELS[kind].model_validate(payload).model_dump(exclude_unset=True)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        event_id = 'DEMO-'+kind.upper()+'-'+hashlib.sha256(
            json.dumps([kind, owner, request_key]).encode()).hexdigest()[:16]
        with self.connect() if connection is None else nullcontext(connection) as db:
            # Serialize concurrent retries before reading or creating the event.
            if not db.in_transaction:
                db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM events WHERE kind=? AND owner=? AND request_key=?',
                             (kind, owner, request_key)).fetchone()
            if old:
                if old['payload_hash'] != digest:
                    return {'status': 'CONFLICT', 'reason_code': 'IDEMPOTENCY_PAYLOAD_MISMATCH'}
                return validate_stored_event(kind, dict(json.loads(old['result']), replayed=True))
            value = dict(result, event_id=event_id, replayed=False)
            value = validate_stored_event(kind, value)
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',
                       (kind, owner, request_key, digest, event_id, encoded, json.dumps(value)))
            return value

    def lookup(self, kind, owner, request_key):
        with self.connect() as db:
            row = db.execute('SELECT result FROM events WHERE kind=? AND owner=? AND request_key=?',
                             (kind, owner, request_key)).fetchone()
        return validate_stored_event(kind, json.loads(row['result'])) if row else {'status': 'UNKNOWN', 'reason_code': 'NO_CONFIRMED_EVENT'}

    def original(self, kind, owner, request_key):
        """Backend/reviewer-only API. Never pass this payload directly to the model."""
        with self.connect() as db:
            row = db.execute('SELECT payload FROM events WHERE kind=? AND owner=? AND request_key=?',
                             (kind, owner, request_key)).fetchone()
        return PAYLOAD_MODELS[kind].model_validate(json.loads(row['payload'])).model_dump(exclude_unset=True) if row else None

    def count(self, kind):
        with self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM events WHERE kind=?', (kind,)).fetchone()[0]

    def find_event(self, kind, event_id):
        """Backend-only lookup; caller must authorize before returning any fields."""
        with self.connect() as db:
            row = db.execute('SELECT payload,result FROM events WHERE kind=? AND event_id=?',
                             (kind,event_id)).fetchone()
        if not row:
            return None
        return {'payload':PAYLOAD_MODELS[kind].model_validate(json.loads(row['payload'])).model_dump(),
                'result':validate_stored_event(kind,json.loads(row['result']))}

    def bind_thread(self, thread_id, owner, binding):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT owner,binding FROM conversation_threads WHERE thread_id=?',(thread_id,)).fetchone()
            if row and (row['owner']!=owner or row['binding']!=binding):
                raise PermissionError('Conversation belongs to another session')
            if not row:db.execute('INSERT INTO conversation_threads VALUES(?,?,?)',(thread_id,owner,binding))

    def begin_turn(self, thread_id, request_key, payload):
        encoded=json.dumps(payload,sort_keys=True);digest=hashlib.sha256(encoded.encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM turns WHERE thread_id=? AND request_key=?',(thread_id,request_key)).fetchone()
            if row:
                if row['payload_hash']!=digest:raise ValueError('Request key already belongs to a different turn')
                return json.loads(row['result']) if row['result'] else None
            db.execute('INSERT INTO turns VALUES(?,?,?,?,NULL)',(thread_id,request_key,encoded,digest))

    def turn_input(self, thread_id, request_key):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM turns WHERE thread_id=? AND request_key=?',(thread_id,request_key)).fetchone()
        if not row:raise ValueError('Unknown turn')
        return json.loads(row['payload'])

    def finish_turn(self, thread_id, request_key, result):
        with self.connect() as db:
            db.execute('UPDATE turns SET result=? WHERE thread_id=? AND request_key=?',
                       (json.dumps(result),thread_id,request_key))

    def save_draft(self, draft_id, thread_id, owner, payload, expires_at):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO drafts VALUES(?,?,?,?,?,\'PENDING\',NULL)',
                       (draft_id,thread_id,owner,json.dumps(payload),expires_at))

    def draft(self, draft_id, thread_id, owner, connection=None):
        with self.connect() if connection is None else nullcontext(connection) as db:
            row=db.execute('SELECT * FROM drafts WHERE draft_id=? AND thread_id=? AND owner=?',
                           (draft_id,thread_id,owner)).fetchone()
        if not row:raise PermissionError('Draft is not available in this conversation')
        return {**dict(row),'payload':json.loads(row['payload']),
                'result':json.loads(row['result']) if row['result'] else None}

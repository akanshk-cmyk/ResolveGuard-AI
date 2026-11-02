"""Existing web tables and compatibility migrations; statement order is preserved."""

def initialize_web_storage(store):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS web_sessions (token_hash TEXT PRIMARY KEY, settings TEXT NOT NULL)')
        if 'active_thread' not in {r['name'] for r in db.execute('PRAGMA table_info(web_sessions)')}:
            db.execute('ALTER TABLE web_sessions ADD COLUMN active_thread TEXT')
        if 'demo_verified' not in {r['name'] for r in db.execute('PRAGMA table_info(web_sessions)')}:
            db.execute('ALTER TABLE web_sessions ADD COLUMN demo_verified INTEGER NOT NULL DEFAULT 0')
        if 'experience_version' not in {r['name'] for r in db.execute('PRAGMA table_info(web_sessions)')}:
            db.execute('ALTER TABLE web_sessions ADD COLUMN experience_version INTEGER NOT NULL DEFAULT 0')
        db.execute('''CREATE TABLE IF NOT EXISTS web_auth_requests (
            pending_id TEXT PRIMARY KEY, source_binding TEXT NOT NULL, request_key TEXT NOT NULL,
            payload TEXT NOT NULL, target_binding TEXT, expires_at TEXT NOT NULL,
            UNIQUE(source_binding,request_key))''')
        db.execute('CREATE TABLE IF NOT EXISTS web_public_context (binding TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS web_public_turns (
            binding TEXT, request_key TEXT, payload_hash TEXT NOT NULL, as_of TEXT NOT NULL,
            source_version TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(binding,request_key))''')
        db.execute('''CREATE TABLE IF NOT EXISTS web_generated_replies (
            binding TEXT, request_key TEXT, evidence_hash TEXT NOT NULL,
            result TEXT, trace TEXT, created_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY(binding,request_key))''')
        if 'created_at' not in {r['name'] for r in db.execute('PRAGMA table_info(web_generated_replies)')}:
            db.execute('ALTER TABLE web_generated_replies ADD COLUMN created_at REAL NOT NULL DEFAULT 0')

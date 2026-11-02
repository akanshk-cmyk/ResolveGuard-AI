"""Optional local operational events. Store aggregates, never customer payloads."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing


def record_observation(result: dict, database: str) -> None:
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    spans = result['trace']['spans']
    event = {'trace_id':result['trace']['trace_id'],
             'timestamp':datetime.now(timezone.utc).isoformat(),
             'latency_ms':spans[0]['latency_ms'] if spans else 0,
             'error_count':len(result.get('errors', []))+sum(bool(s.get('error')) for s in spans),
             'execution_mode':result['execution_mode'],
             'input_tokens':result.get('input_tokens'), 'output_tokens':result.get('output_tokens'),
             'model_cost_usd':result.get('model_cost_usd'),
             'span_count':len(spans)}
    event['journey_scope']=result.get('journey_scope','WORKFLOW')
    if result.get('generation'):
        from .telemetry import generation_metrics
        event['generation']=generation_metrics(result['generation'])
    with closing(sqlite3.connect(path, timeout=1)) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, event TEXT NOT NULL)')
        conn.execute('INSERT INTO observations(event) VALUES (?)', (json.dumps(event),))
        conn.execute('DELETE FROM observations WHERE id <= (SELECT COALESCE(MAX(id),0)-10000 FROM observations)')


def read_observations(database: str | None) -> list[dict]:
    if not database or not Path(database).is_file():
        return []
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True, timeout=1)) as conn:
        try:
            return [json.loads(row[0]) for row in conn.execute('SELECT event FROM observations ORDER BY id DESC LIMIT 200')]
        except sqlite3.OperationalError:
            return []


def observe(result: dict) -> None:
    """Failures in observability must not alter customer decisions or responses."""
    database = os.environ.get('RESOLVEGUARD_MONITOR_DB')
    if database:
        try:
            record_observation(result, database)
        except Exception:
            import logging
            logging.getLogger(__name__).warning('OBSERVABILITY_LOCAL_WRITE_FAILED')
    from .eval_config import cloud_tracing_enabled
    if cloud_tracing_enabled():
        try:
            from .runtime_export import enqueue_trace
            enqueue_trace(result['trace'])
        except Exception:
            import logging
            logging.getLogger(__name__).warning('OBSERVABILITY_CLOUD_ENQUEUE_FAILED')

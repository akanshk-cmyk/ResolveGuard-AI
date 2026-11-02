"""Shared inert defaults and environment parsing; importing never loads .env."""
import os
from pathlib import Path
from collections.abc import Collection

NEBIUS_API_BASE = 'https://api.tokenfactory.nebius.com/v1'
NEBIUS_CHAT_ENDPOINT = NEBIUS_API_BASE + '/chat/completions'
DEFAULT_CHAT_MODEL = 'zai-org/GLM-5.3-Flash'
DEFAULT_EMBEDDING_MODEL = 'Qwen/Qwen3-Embedding-8B'

EVALUATION_ENVIRONMENT_KEYS = frozenset({
    'NEBIUS_API_KEY', 'NEBIUS_MODEL', 'LANGSMITH_API_KEY',
    'LANGSMITH_PROJECT', 'LANGSMITH_ENDPOINT', 'LANGSMITH_TRACING',
    'RESOLVEGUARD_CLOUD_TRACING', 'RESOLVEGUARD_MONITOR_DB',
    'RESOLVEGUARD_JUDGE_MODEL', 'RESOLVEGUARD_EMBEDDING_MODEL',
    'RESOLVEGUARD_DASHBOARD_TOKEN',
})
REPLY_ENVIRONMENT_KEYS = frozenset({
    'RESOLVEGUARD_REPLY_MODE', 'RESOLVEGUARD_REPLY_TIMEOUT',
    'RESOLVEGUARD_REPLY_BUDGET_MS', 'NEBIUS_API_KEY',
})


def load_environment_entries(path: Path, allowed: Collection[str]) -> None:
    """Load literal values, preserving caller guards and process precedence."""
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key, separator, value = line.partition('=')
        key = key.strip()
        if separator and key in allowed:
            os.environ.setdefault(key, value.strip().strip('\"\''))

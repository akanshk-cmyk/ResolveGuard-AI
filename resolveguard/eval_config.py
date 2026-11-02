"""Explicit evaluation configuration; never logs credentials or mutates chat defaults."""
import json
import os
from pathlib import Path
from .configuration import EVALUATION_ENVIRONMENT_KEYS, NEBIUS_API_BASE, load_environment_entries

ROOT = Path(__file__).resolve().parents[1]


def load_eval_environment(path: Path | None = None) -> None:
    """Read simple KEY=value entries, preserving existing process environment.

    No shell evaluation, interpolation, or implicit loading during customer chat.
    """
    path = path or ROOT / '.env'
    if not path.exists():
        return
    load_environment_entries(path, EVALUATION_ENVIRONMENT_KEYS)


def cloud_tracing_enabled() -> bool:
    return (os.environ.get('LANGSMITH_TRACING', '').lower() == 'true'
            and os.environ.get('RESOLVEGUARD_CLOUD_TRACING', '').lower() == 'true')


def evaluation_client(usage: list | None = None):
    """Nebius-only evaluation client. No accidental fallback to another provider."""
    if not os.environ.get('NEBIUS_API_KEY'):
        raise RuntimeError('NEBIUS_API_KEY is required for semantic evaluation')
    try:
        from openai import AsyncOpenAI
        import httpx
    except ImportError as exc:
        raise RuntimeError('Install requirements-evals.txt for semantic evaluation') from exc
    async def capture_usage(response):
        if usage is None:
            return
        await response.aread()
        event = {'http_status':response.status_code}
        try:
            request = json.loads(response.request.content)
            body = response.json()
            tokens = body.get('usage') or {}
            event.update(model=request.get('model'),
                input_tokens=tokens.get('prompt_tokens'),
                output_tokens=tokens.get('completion_tokens', 0 if response.request.url.path.endswith('/embeddings') else None))
        except (ValueError, TypeError, AttributeError):
            event['usage_available'] = False
        usage.append(event)

    return AsyncOpenAI(api_key=os.environ['NEBIUS_API_KEY'],
                       base_url=NEBIUS_API_BASE,
                       max_retries=1, timeout=45,
                       http_client=httpx.AsyncClient(follow_redirects=False, timeout=45,
                           event_hooks={'response':[capture_usage]}))

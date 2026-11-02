"""Bounded asynchronous opt-in cloud export; never blocks customer requests."""
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from .cloud_privacy import cloud_trace

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='resolveguard-traces')
_slots = BoundedSemaphore(32)
_logger = logging.getLogger(__name__)


def _publish(trace: dict) -> None:
    try:
        from .langsmith_integration import publish_trace
        publish_trace(trace)
    except Exception:
        _logger.warning('OBSERVABILITY_CLOUD_EXPORT_FAILED')
    finally:
        _slots.release()


def enqueue_trace(trace: dict) -> None:
    if not _slots.acquire(blocking=False):
        _logger.warning('OBSERVABILITY_CLOUD_QUEUE_FULL')
        return
    try:
        _executor.submit(_publish, cloud_trace(trace))
    except Exception:
        _slots.release()
        _logger.warning('OBSERVABILITY_CLOUD_QUEUE_UNAVAILABLE')

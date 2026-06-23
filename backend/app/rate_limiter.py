"""
Simple in-memory sliding-window rate limiter, keyed per user_id.

This is the basic abuse-prevention control: it stops a single user (or a
script acting as one) from flooding /transaction to inflate their ranking
through sheer request volume, independent of the idempotency-key dedup
(which only catches *identical* retried requests, not many distinct ones).

Trade-off: state lives in process memory, so it resets on restart and does
not coordinate across multiple processes/instances. For a single-instance
deployment (as described in the README) that's an acceptable trade-off for
a take-home; a production multi-instance deployment would move this to
Redis (e.g. INCR + EXPIRE) so all instances share one counter.
"""

import threading
import time
from collections import defaultdict, deque

from . import config

_lock = threading.Lock()
_requests_by_user: dict[str, deque] = defaultdict(deque)


def check_and_record(user_id: str) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    now = time.time()
    window_start = now - config.RATE_LIMIT_WINDOW_SECONDS
    with _lock:
        q = _requests_by_user[user_id]
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= config.RATE_LIMIT_MAX_REQUESTS:
            return False
        q.append(now)
        return True

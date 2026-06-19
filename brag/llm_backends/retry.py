"""Retry helper with error classification.

Rate limits get long backoff (limits reset per minute), transient network
errors get short backoff, everything else fails fast. Ported from a system
where missing this classification cost real data (chunks lost to transient
DNS hiccups that were treated as fatal).
"""

import random
import time

RATE_LIMIT_MARKERS = ("429", "503", "529", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded")
NETWORK_MARKERS = (
    "Network is unreachable", "nodename nor servname", "Connection refused",
    "Connection reset", "Connection aborted", "Read timed out",
    "ConnectionError", "EOF occurred", "Temporary failure in name resolution",
)


def call_with_retry(fn, max_retries: int = 5, label: str = "",
                    deadline_seconds: float = 420):
    """Call ``fn`` with classified backoff. ``deadline_seconds`` caps the TOTAL
    time spent waiting across retries (generous by default so legitimate
    per-minute rate-limit recovery still completes) — without it, five
    rate-limit backoffs could hang a single call for many minutes."""
    start = time.monotonic()
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — classified below
            err = str(e)
            is_rate_limit = any(m in err for m in RATE_LIMIT_MARKERS)
            is_network = any(m in err for m in NETWORK_MARKERS)
            last_attempt = attempt == max_retries - 1

            if is_rate_limit and not last_attempt:
                wait = max(60, min(180, 60 * (attempt + 1))) + random.uniform(0, 5)
                kind = "rate limit"
            elif is_network and not last_attempt:
                wait = min(30, 3 * (attempt + 1) * (1.5 ** attempt)) + random.uniform(0, 2)
                kind = "network error"
            else:
                print(f"  failed ({label}): {err[:120]}")
                return None

            # Don't start a backoff we can't afford within the overall deadline.
            if time.monotonic() - start + wait > deadline_seconds:
                print(f"  giving up ({label}) — would exceed {deadline_seconds:.0f}s deadline")
                return None
            print(f"  {kind} ({label}), retry {attempt + 1}/{max_retries} in {wait:.0f}s")
            time.sleep(wait)
    return None

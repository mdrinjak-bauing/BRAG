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


def call_with_retry(fn, max_retries: int = 5, label: str = ""):
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
                print(f"  rate limit ({label}), retry {attempt + 1}/{max_retries} in {wait:.0f}s")
                time.sleep(wait)
            elif is_network and not last_attempt:
                wait = min(30, 3 * (attempt + 1) * (1.5 ** attempt)) + random.uniform(0, 2)
                print(f"  network error ({label}), retry {attempt + 1}/{max_retries} in {wait:.0f}s")
                time.sleep(wait)
            else:
                print(f"  failed ({label}): {err[:120]}")
                return None
    return None

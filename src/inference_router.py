"""Route inference requests: the local (k3s) service first, Cloud Run as overflow.

Local inference runs one request at a time well on a small node. When
`max_local` requests are already in flight there, or the local service is
down, the request goes to the overflow URL (a scale-to-zero Cloud Run service)
instead of queueing. Without an overflow URL everything goes to local.
"""

import logging
import threading
from dataclasses import dataclass, field

import requests

logger = logging.getLogger("main")

# Statuses that mean "local could not serve this", not "the request is bad".
RETRYABLE = {502, 503, 504}


@dataclass
class InferenceRouter:
    local_url: str
    overflow_url: str | None = None
    api_key: str | None = None
    max_local: int = 1
    timeout: float = 120
    _inflight: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def inflight(self) -> int:
        return self._inflight

    def _try_acquire_local(self) -> bool:
        with self._lock:
            if self.overflow_url is None or self._inflight < self.max_local:
                self._inflight += 1
                return True
            return False

    def _release_local(self) -> None:
        with self._lock:
            self._inflight -= 1

    def _post(self, url: str, payload: dict) -> dict:
        headers = {"X-Api-Key": self.api_key} if self.api_key else {}
        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def predict(self, payload: dict) -> tuple[dict, str]:
        """Return (response JSON, backend name: "local" or "overflow")."""
        if self._try_acquire_local():
            try:
                return self._post(self.local_url, payload), "local"
            except (requests.ConnectionError, requests.Timeout) as e:
                if not self.overflow_url:
                    raise
                logger.warning(f"local inference unavailable ({e!r}); using overflow")
            except requests.HTTPError as e:
                if not self.overflow_url or e.response.status_code not in RETRYABLE:
                    raise
                logger.warning(f"local inference returned {e.response.status_code}; using overflow")
            finally:
                self._release_local()
        return self._post(self.overflow_url, payload), "overflow"

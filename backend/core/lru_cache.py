"""Thread-safe LRU cache with TTL."""
import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                self.misses += 1
                return None
            value, ts = self._data[key]
            if self.ttl_seconds > 0 and (time.time() - ts) > self.ttl_seconds:
                del self._data[key]
                self.expirations += 1
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = (value, time.time())
                return
            self._data[key] = (value, time.time())
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)
                self.evictions += 1

    def invalidate(self, prefix: str) -> int:
        """Invalidate all keys starting with prefix. Returns count invalidated."""
        with self._lock:
            keys = [k for k in self._data.keys() if k.startswith(prefix)]
            for k in keys:
                del self._data[k]
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 4) if total > 0 else 0.0,
                "evictions": self.evictions,
                "expirations": self.expirations,
            }

"""Segmented rate limiter for Ozon API.

Ozon enforces "rate limit per second" (code 8) at the Client-ID level.
This limiter spaces all calls with minimum intervals and backs off
aggressively after any 429.
"""

import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)


class OzonRateLimiter:
    """Segmented rate limiter with exponential backoff on 429.

    - Minimum gap between calls: 5 seconds
    - After 429: cooldown doubles each time (30s -> 60s -> 120s -> ...)
    - Max 60 calls per minute (sliding window)
    """

    def __init__(self) -> None:
        self.min_interval: float = 15.0       # seconds between any two calls
        self.max_per_minute: int = 60
        self._last_call: float = 0.0
        self._call_times: list[float] = []
        # Load persisted cooldown from file (survives restart)
        self._cooldown_file = "ozon_cooldown.txt"
        self._cooldown_until: float = self._load_cooldown()
        self._cooldown_seconds: float = 30.0  # doubles on each 429
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    def _load_cooldown(self) -> float:
        try:
            with open(self._cooldown_file) as f:
                return float(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0.0

    def _save_cooldown(self, until: float) -> None:
        try:
            with open(self._cooldown_file, "w") as f:
                f.write(str(until))
        except OSError:
            pass

    async def acquire(self) -> None:
        """Wait until it's safe to make the next API call."""
        async with self._lock:
            now = time.monotonic()

            # 1. Cooldown from previous 429
            if now < self._cooldown_until:
                wait = self._cooldown_until - now
                logger.info("Cooldown active, waiting %.0fs", wait)
                await asyncio.sleep(wait)
                now = time.monotonic()

            # 2. Minimum interval since last call
            gap = now - self._last_call
            if gap < self.min_interval:
                await asyncio.sleep(self.min_interval - gap)
                now = time.monotonic()

            # 3. Per-minute sliding window
            cutoff = now - 60.0
            self._call_times = [t for t in self._call_times if t > cutoff]
            if len(self._call_times) >= self.max_per_minute:
                wait = self._call_times[0] + 60.0 - now + 0.5
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._call_times = [t for t in self._call_times if t > now - 60.0]

            # 4. Record
            self._call_times.append(now)
            self._last_call = now

    def report_429(self) -> None:
        """Trigger cooldown after a 429, doubling each time (thread-safe)."""
        with self._sync_lock:
            self._cooldown_until = time.monotonic() + self._cooldown_seconds
            self._save_cooldown(self._cooldown_until)
            logger.warning("429 received, cooldown %.0fs", self._cooldown_seconds)
            self._cooldown_seconds = min(self._cooldown_seconds * 2, 300.0)

    def report_success(self) -> None:
        """Reset cooldown backoff on success (thread-safe)."""
        with self._sync_lock:
            self._cooldown_seconds = max(self._cooldown_seconds / 2, 30.0)
            self._save_cooldown(0.0)

    async def __aenter__(self) -> "OzonRateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


# Singleton
ozon_rate_limiter = OzonRateLimiter()

import time
from collections import defaultdict, deque

import app.core.config as config


class SlidingWindowRateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, max_attempts=None, window_seconds=None):
        self.max_attempts = max_attempts if max_attempts is not None else getattr(config, "LOGIN_RATE_LIMIT", 5)
        self.window_seconds = window_seconds if window_seconds is not None else getattr(config, "LOGIN_RATE_WINDOW_SECONDS", 60)
        self._attempts = defaultdict(deque)

    def _now(self):
        return time.time()

    def _prune(self, key, now):
        window = self._attempts.get(key)
        if not window:
            return

        cutoff = now - self.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()

        if not window:
            self._attempts.pop(key, None)

    def is_allowed(self, key):
        """Return True if the request is allowed under the rate limit."""
        now = self._now()
        self._prune(key, now)

        attempts = self._attempts[key]
        if len(attempts) >= self.max_attempts:
            return False

        attempts.append(now)
        return True

    def remaining(self, key):
        """Return the remaining attempts for a key."""
        now = self._now()
        self._prune(key, now)
        return max(0, self.max_attempts - len(self._attempts.get(key, ())))

    def reset(self, key=None):
        """Reset the rate limit state for a key or all keys."""
        if key is None:
            self._attempts.clear()
        else:
            self._attempts.pop(key, None)


login_rate_limiter = SlidingWindowRateLimiter()

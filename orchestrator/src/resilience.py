"""
Resilience Patterns — Circuit breaker, retry, fallback, rate limiting.

Reusable resilience primitives for external API calls (LLM providers,
GitHub, arXiv, HuggingFace, etc.). Designed to be composed together:

    breaker = CircuitBreaker("anthropic")
    limiter = RateLimiter("anthropic", max_calls=50)

    @retry_with_backoff(max_retries=3)
    async def call_api():
        await limiter.acquire()
        return await breaker.call(actual_api_fn)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CircuitOpenError(Exception):
    """Raised when a circuit breaker is OPEN and rejecting calls."""

    def __init__(self, name: str, retry_after: float = 0.0) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{name}' is OPEN — call rejected. "
            f"Retry after {retry_after:.1f}s."
        )


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitStats:
    total_calls: int = 0
    failures: int = 0
    successes: int = 0
    last_failure_time: float | None = None
    last_state_change: float = field(default_factory=time.monotonic)


class CircuitBreaker:
    """
    Three-state circuit breaker for external service calls.

    CLOSED  -> normal operation; tracks consecutive failures.
    OPEN    -> all calls rejected immediately; waits recovery_timeout.
    HALF_OPEN -> allows up to half_open_max test calls.
               Success -> CLOSED.  Failure -> OPEN again.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 2,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_calls = 0
        self._opened_at: float = 0.0
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()

    # -- public properties --------------------------------------------------

    @property
    def state(self) -> CircuitState:
        # Note: auto-transition is now handled inside call() under lock.
        # This property returns the current state without side effects.
        return self._state

    @property
    def stats(self) -> CircuitStats:
        return self._stats

    # -- public methods -----------------------------------------------------

    async def call(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        """Wrap an async function call with circuit-breaker logic."""
        async with self._lock:
            # Auto-transition OPEN -> HALF_OPEN after recovery_timeout (under lock)
            if (
                self._state == CircuitState.OPEN
                and time.monotonic() - self._opened_at >= self.recovery_timeout
            ):
                self._transition(CircuitState.HALF_OPEN)

            current = self._state

            if current == CircuitState.OPEN:
                retry_after = self.recovery_timeout - (time.monotonic() - self._opened_at)
                raise CircuitOpenError(self.name, max(retry_after, 0.0))

            if current == CircuitState.HALF_OPEN and self._half_open_calls >= self.half_open_max:
                raise CircuitOpenError(self.name, self.recovery_timeout)

            if current == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

            self._stats.total_calls += 1

        # Execute outside the lock so we don't block other callers
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            await self._on_failure(exc)
            raise
        else:
            await self._on_success()
            return result

    def reset(self) -> None:
        """Force circuit back to CLOSED state."""
        self._transition(CircuitState.CLOSED)
        self._consecutive_failures = 0
        self._half_open_calls = 0
        logger.info("Circuit '%s' manually reset to CLOSED.", self.name)

    # -- internals ----------------------------------------------------------

    async def _on_success(self) -> None:
        async with self._lock:
            self._stats.successes += 1
            if self._state == CircuitState.HALF_OPEN:
                # Recovery confirmed
                self._transition(CircuitState.CLOSED)
                self._consecutive_failures = 0
                self._half_open_calls = 0
                logger.info("Circuit '%s' recovered -> CLOSED.", self.name)
            else:
                self._consecutive_failures = 0

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._stats.failures += 1
            self._stats.last_failure_time = time.monotonic()
            self._consecutive_failures += 1

            if self._state == CircuitState.HALF_OPEN:
                # Test call failed — reopen
                self._transition(CircuitState.OPEN)
                self._half_open_calls = 0
                logger.warning(
                    "Circuit '%s' HALF_OPEN test failed (%s) -> OPEN.",
                    self.name, exc,
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._consecutive_failures >= self.failure_threshold
            ):
                self._transition(CircuitState.OPEN)
                logger.warning(
                    "Circuit '%s' hit %d failures -> OPEN.",
                    self.name, self._consecutive_failures,
                )

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._stats.last_state_change = time.monotonic()
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
        if old != new_state:
            logger.debug("Circuit '%s': %s -> %s", self.name, old.value, new_state.value)


# ---------------------------------------------------------------------------
# retry_with_backoff (decorator / wrapper)
# ---------------------------------------------------------------------------

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """
    Decorator: exponential backoff with jitter.

    Usage as decorator:
        @retry_with_backoff(max_retries=3)
        async def my_call(): ...

    Or as a direct wrapper:
        result = await retry_with_backoff(max_retries=2)(my_call)(arg1, arg2)
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (2 ** attempt) + random.random(),
                            max_delay,
                        )
                        logger.debug(
                            "Retry %d/%d for %s after %.2fs (error: %s)",
                            attempt + 1, max_retries, fn.__qualname__, delay, exc,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            "All %d retries exhausted for %s. Last error: %s",
                            max_retries, fn.__qualname__, exc,
                        )
            raise last_exc  # type: ignore[misc]

        wrapper.__qualname__ = fn.__qualname__
        wrapper.__name__ = getattr(fn, "__name__", "unknown")
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# FallbackChain
# ---------------------------------------------------------------------------

class FallbackChain:
    """
    Tries a sequence of async callables in order. Returns the first
    successful result; raises the last exception if all fail.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._chain: list[tuple[str, Callable[..., Awaitable[Any]]]] = []

    def add(self, fn: Callable[..., Awaitable[Any]], label: str) -> "FallbackChain":
        """Add a fallback function. Returns self for chaining."""
        self._chain.append((label, fn))
        return self

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Try each function in order; return first success."""
        if not self._chain:
            raise RuntimeError(f"FallbackChain '{self.name}' has no functions registered.")

        last_exc: Exception | None = None
        for label, fn in self._chain:
            try:
                result = await fn(*args, **kwargs)
                logger.info(
                    "FallbackChain '%s' succeeded with '%s'.", self.name, label
                )
                return result
            except Exception as exc:
                logger.debug(
                    "FallbackChain '%s': '%s' failed (%s), trying next.",
                    self.name, label, exc,
                )
                last_exc = exc

        logger.error(
            "FallbackChain '%s': all %d fallbacks failed.", self.name, len(self._chain)
        )
        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RateLimiter (token bucket)
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Simple token-bucket rate limiter.

    Allows max_calls within each rolling period (seconds). acquire() blocks
    until a token is available; can_proceed() is a non-blocking check.
    """

    def __init__(self, name: str, max_calls: int = 60, period: float = 60.0) -> None:
        self.name = name
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    def _prune(self) -> None:
        """Remove expired timestamps."""
        cutoff = time.monotonic() - self.period
        self._calls = [t for t in self._calls if t > cutoff]

    def can_proceed(self) -> bool:
        """Non-blocking check: is a token available right now?"""
        self._prune()
        return len(self._calls) < self.max_calls

    async def acquire(self) -> None:
        """Block until a rate-limit token is available, then consume it."""
        while True:
            async with self._lock:
                self._prune()
                if len(self._calls) < self.max_calls:
                    self._calls.append(time.monotonic())
                    return

            # Wait until the oldest call expires
            if self._calls:
                wait = self._calls[0] - (time.monotonic() - self.period)
                if wait > 0:
                    logger.debug(
                        "RateLimiter '%s': limit reached, waiting %.2fs.",
                        self.name, wait,
                    )
                    await asyncio.sleep(wait)
            else:
                await asyncio.sleep(0.01)

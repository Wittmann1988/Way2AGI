"""
Semantic-aware LLM response cache — dual backend (file + Redis).

On Desktop/Docker: Uses Redis for shared, fast caching across services.
On Mobile/Standalone: Falls back to file-based JSON storage.

Caches LLM call results keyed by model_id + normalized prompt hash.
Supports TTL-based expiry, stats tracking, and transparent wrapping
of LLMCallFn callables.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from typing import Callable, Awaitable

# Define locally to avoid circular import with composer.py
LLMCallFn = Callable[[str, str, str], Awaitable[str]]


class LLMCache:
    """LLM response cache with file backend + optional Redis backend."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        max_entries: int = 1000,
        ttl_hours: int = 24,
        redis_url: str | None = None,
    ) -> None:
        self.cache_dir = Path(
            cache_dir or os.path.expanduser("~/.way2agi/cache/llm")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self.ttl_hours = ttl_hours
        self._hits = 0
        self._misses = 0

        # Redis backend (optional, for Docker/Desktop deployment)
        self._redis = None
        self._redis_url = redis_url or os.environ.get("REDIS_URL")

    async def _get_redis(self):
        """Lazy-init Redis connection."""
        if self._redis is not None:
            return self._redis
        if not self._redis_url:
            return None
        try:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            return self._redis
        except Exception:
            self._redis_url = None  # Disable Redis on failure
            return None

    # ── Key generation ──────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize prompt for near-duplicate detection."""
        text = text.strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _make_hash(model_id: str, prompt: str, system: str = "") -> str:
        """SHA-256 hash of model_id + system + normalized prompt."""
        normalized = LLMCache._normalize(prompt)
        norm_system = LLMCache._normalize(system)
        raw = f"{model_id}||{norm_system}||{normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _entry_path(self, prompt_hash: str) -> Path:
        return self.cache_dir / f"{prompt_hash}.json"

    # ── Core operations ─────────────────────────────────────────────

    def get(self, model_id: str, prompt: str, system: str = "") -> str | None:
        """Return cached response or None on miss (file backend)."""
        prompt_hash = self._make_hash(model_id, prompt, system)
        path = self._entry_path(prompt_hash)

        if not path.exists():
            self._misses += 1
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._misses += 1
            return None

        # Check TTL
        created = datetime.fromisoformat(data["created_at"])
        age_hours = (
            datetime.now(timezone.utc) - created
        ).total_seconds() / 3600
        if age_hours > self.ttl_hours:
            path.unlink(missing_ok=True)
            self._misses += 1
            return None

        self._hits += 1
        return data["response"]

    async def aget(self, model_id: str, prompt: str, system: str = "") -> str | None:
        """Async get — tries Redis first, then file fallback."""
        prompt_hash = self._make_hash(model_id, prompt, system)

        # Try Redis first
        redis = await self._get_redis()
        if redis:
            key = f"llm:{prompt_hash}"
            cached = await redis.get(key)
            if cached is not None:
                self._hits += 1
                return json.loads(cached)

        # Fall back to file
        return self.get(model_id, prompt, system)

    def put(
        self,
        model_id: str,
        prompt: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a response in the file cache (atomic write)."""
        prompt_hash = self._make_hash(model_id, prompt)
        entry = {
            "model_id": model_id,
            "prompt_hash": prompt_hash,
            "prompt_preview": prompt[:100],
            "response": response,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        # Enforce max_entries before writing
        self._maybe_evict()

        # Atomic write: write to temp file then rename
        path = self._entry_path(prompt_hash)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.cache_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    async def aput(
        self,
        model_id: str,
        prompt: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Async put — writes to both Redis and file."""
        # File backend (always)
        self.put(model_id, prompt, response, metadata)

        # Redis backend (if available)
        redis = await self._get_redis()
        if redis:
            prompt_hash = self._make_hash(model_id, prompt)
            key = f"llm:{prompt_hash}"
            ttl_seconds = self.ttl_hours * 3600
            await redis.setex(key, ttl_seconds, json.dumps(response))

    def wrap(self, llm_fn: LLMCallFn) -> LLMCallFn:
        """
        Wrap an LLM call function with caching.

        The wrapped function checks cache first (keyed on model_id + prompt).
        On hit, returns cached response. On miss, calls the real function,
        caches the result, and returns it.
        """
        cache = self

        async def cached_llm_fn(
            model_id: str, system: str, prompt: str
        ) -> str:
            cached = cache.get(model_id, prompt, system)
            if cached is not None:
                return cached

            response = await llm_fn(model_id, system, prompt)
            cache.put(
                model_id,
                prompt,
                response,
                metadata={"system_preview": system[:100], "system_hash": system},
            )
            return response

        return cached_llm_fn

    # ── Maintenance ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        entries = list(self.cache_dir.glob("*.json"))
        total_size = sum(e.stat().st_size for e in entries)
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (self._hits / total) if total > 0 else 0.0,
            "total_entries": len(entries),
            "cache_size_bytes": total_size,
            "redis_enabled": self._redis is not None,
        }

    def evict_expired(self) -> int:
        """Remove entries older than TTL. Returns count removed."""
        removed = 0
        now = datetime.now(timezone.utc)
        for path in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                created = datetime.fromisoformat(data["created_at"])
                age_hours = (now - created).total_seconds() / 3600
                if age_hours > self.ttl_hours:
                    path.unlink()
                    removed += 1
            except (json.JSONDecodeError, OSError, KeyError):
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear(self) -> None:
        """Remove all cache entries."""
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)
        self._hits = 0
        self._misses = 0

    async def aclose(self) -> None:
        """Close Redis connection if open."""
        if self._redis:
            await self._redis.aclose()

    # ── Internal ────────────────────────────────────────────────────

    def _maybe_evict(self) -> None:
        """If at max capacity, remove oldest entries to make room."""
        entries = sorted(
            self.cache_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        while len(entries) >= self.max_entries:
            entries[0].unlink(missing_ok=True)
            entries.pop(0)

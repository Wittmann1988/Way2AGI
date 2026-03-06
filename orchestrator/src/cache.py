"""
Semantic-aware LLM response cache with file-based JSON storage.

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
LLMCallFn = Callable[[str, str], Awaitable[str]]


class LLMCache:
    """File-based LLM response cache with near-duplicate detection."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        max_entries: int = 1000,
        ttl_hours: int = 24,
    ) -> None:
        self.cache_dir = Path(
            cache_dir or os.path.expanduser("~/.way2agi/cache/llm")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self.ttl_hours = ttl_hours
        self._hits = 0
        self._misses = 0

    # ── Key generation ──────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize prompt for near-duplicate detection."""
        text = text.strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _make_hash(model_id: str, prompt: str) -> str:
        """SHA-256 hash of model_id + normalized prompt, first 16 chars."""
        normalized = LLMCache._normalize(prompt)
        raw = f"{model_id}||{normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _entry_path(self, prompt_hash: str) -> Path:
        return self.cache_dir / f"{prompt_hash}.json"

    # ── Core operations ─────────────────────────────────────────────

    def get(self, model_id: str, prompt: str) -> str | None:
        """Return cached response or None on miss."""
        prompt_hash = self._make_hash(model_id, prompt)
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

    def put(
        self,
        model_id: str,
        prompt: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a response in the cache (atomic write)."""
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
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def wrap(self, llm_fn: LLMCallFn) -> LLMCallFn:
        """
        Wrap an LLM call function with caching.

        The wrapped function checks cache first (keyed on model_id + prompt).
        On hit, returns cached response. On miss, calls the real function,
        caches the result, and returns it.

        Note: the system prompt is intentionally NOT part of the cache key.
        The same model+prompt combination is expected to have the same system
        prompt in practice, and including it would reduce hit rates for
        minor system prompt variations.
        """
        cache = self

        async def cached_llm_fn(
            model_id: str, system: str, prompt: str
        ) -> str:
            cached = cache.get(model_id, prompt)
            if cached is not None:
                return cached

            response = await llm_fn(model_id, system, prompt)
            cache.put(
                model_id,
                prompt,
                response,
                metadata={"system_preview": system[:100]},
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
                # Corrupt entry — remove it
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear(self) -> None:
        """Remove all cache entries."""
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)
        self._hits = 0
        self._misses = 0

    # ── Internal ────────────────────────────────────────────────────

    def _maybe_evict(self) -> None:
        """If at max capacity, remove oldest entries to make room."""
        entries = sorted(
            self.cache_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        # Remove oldest entries if we're at the limit
        while len(entries) >= self.max_entries:
            entries[0].unlink(missing_ok=True)
            entries.pop(0)

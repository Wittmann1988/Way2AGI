"""Way2AGI Configuration Manager."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path.home() / ".way2agi"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


class Way2AGIConfig:
    """Manages ~/.way2agi/config.json."""

    def __init__(self, config_path: Path | None = None):
        self.path = config_path or DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = self._defaults()
        if self.path.exists():
            with open(self.path) as f:
                saved = json.load(f)
            self._data = _deep_merge(self._defaults(), saved)

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "version": "1.0.0",
            "user_name": "User",
            "language": "de",
            "provider": "openrouter",
            "model": "qwen/qwen3-coder",
            "providers": {
                "openrouter": {
                    "api_key": "",
                    "base_url": "https://openrouter.ai/api/v1",
                    "models": [
                        "qwen/qwen3-coder",
                        "stepfun/step-2-16k-exp",
                    ],
                },
                "groq": {
                    "api_key": "",
                    "base_url": "https://api.groq.com/openai/v1",
                    "models": ["moonshotai/kimi-k2"],
                },
                "ollama": {
                    "api_key": "",
                    "base_url": "http://localhost:11434/v1",
                    "models": [],
                },
                "anthropic": {
                    "api_key": "",
                    "base_url": "https://api.anthropic.com/v1",
                    "models": [
                        "claude-sonnet-4-6",
                        "claude-haiku-4-5",
                    ],
                },
                "openai": {
                    "api_key": "",
                    "base_url": "https://api.openai.com/v1",
                    "models": ["gpt-4o", "gpt-4o-mini"],
                },
                "google": {
                    "api_key": "",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                    "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
                },
                "custom": {
                    "api_key": "",
                    "base_url": "",
                    "models": [],
                },
            },
            "memory": {
                "enabled": True,
                "db_path": str(DEFAULT_CONFIG_DIR / "memory.db"),
                "auto_store": True,
                "auto_recall": True,
                "recall_top_k": 3,
            },
            "autonomy_level": "balanced",
            "drive_weights": {
                "curiosity": 0.7,
                "competence": 0.5,
                "social": 0.4,
                "autonomy": 0.3,
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        d = self._data
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    @property
    def provider(self) -> str:
        return self._data["provider"]

    @property
    def model(self) -> str:
        return self._data["model"]

    @property
    def provider_config(self) -> dict[str, Any]:
        return self._data["providers"].get(self.provider, {})

    @property
    def is_first_run(self) -> bool:
        return not self.path.exists()


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

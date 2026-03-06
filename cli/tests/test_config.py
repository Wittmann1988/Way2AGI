"""Tests for Way2AGI Config Manager."""
import json
from pathlib import Path
from cli.config import Way2AGIConfig


def test_default_config_has_free_providers():
    cfg = Way2AGIConfig._defaults()
    assert cfg["provider"] == "openrouter"
    assert cfg["model"] == "qwen/qwen3-coder"
    assert cfg["providers"]["openrouter"]["api_key"] == ""


def test_save_and_load(tmp_path):
    path = tmp_path / "config.json"
    cfg = Way2AGIConfig(config_path=path)
    cfg.set("provider", "ollama")
    cfg.save()
    cfg2 = Way2AGIConfig(config_path=path)
    assert cfg2.get("provider") == "ollama"


def test_dot_notation_get():
    cfg = Way2AGIConfig._defaults()
    config = Way2AGIConfig.__new__(Way2AGIConfig)
    config._data = cfg
    config.path = Path("/tmp/nonexistent.json")
    assert config.get("memory.enabled") is True
    assert config.get("memory.recall_top_k") == 3
    assert config.get("nonexistent.key", "fallback") == "fallback"


def test_dot_notation_set(tmp_path):
    path = tmp_path / "config.json"
    cfg = Way2AGIConfig(config_path=path)
    cfg.set("memory.recall_top_k", 5)
    assert cfg.get("memory.recall_top_k") == 5


def test_deep_merge_preserves_defaults(tmp_path):
    path = tmp_path / "config.json"
    # Save partial config
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"provider": "groq", "user_name": "Erik"}, f)
    cfg = Way2AGIConfig(config_path=path)
    # Overridden
    assert cfg.provider == "groq"
    assert cfg.get("user_name") == "Erik"
    # Defaults preserved
    assert cfg.get("memory.enabled") is True
    assert "anthropic" in cfg._data["providers"]


def test_provider_config():
    cfg = Way2AGIConfig(config_path=Path("/tmp/nonexistent_way2agi.json"))
    assert cfg.provider == "openrouter"
    assert "base_url" in cfg.provider_config
    assert "models" in cfg.provider_config

"""First-run experience and environment check."""
from __future__ import annotations

import sys
from pathlib import Path
from cli.config import Way2AGIConfig, DEFAULT_CONFIG_DIR


def ensure_data_dir() -> None:
    """Create ~/.way2agi/ if it doesn't exist."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def check_python_version() -> bool:
    """Require Python 3.11+."""
    return sys.version_info >= (3, 11)


def is_first_run() -> bool:
    """Check if config exists."""
    return not (DEFAULT_CONFIG_DIR / "config.json").exists()


def run_first_time_setup(config: Way2AGIConfig) -> None:
    """Minimal first-run: create config with defaults, print welcome."""
    ensure_data_dir()
    config.save()

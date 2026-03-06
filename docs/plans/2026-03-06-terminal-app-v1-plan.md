# Way2AGI Terminal App v1.0 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Installierbare Python Terminal-App mit Dashboard, Chat, Settings, Memory und Diagnostics.

**Architecture:** Python/Textual TUI als Frontend, httpx fuer LLM-API-Calls (OpenAI-kompatibles Format), elias-memory fuer persistentes Memory, config in ~/.way2agi/config.json. Kein Gateway/Node.js in v1 — reines Python.

**Tech Stack:** Python 3.11+, textual, httpx, rich, elias-memory, click

---

### Task 1: Projekt-Skeleton + Entry-Point

**Files:**
- Create: `cli/__init__.py`
- Create: `cli/__main__.py`
- Create: `cli/app.py`
- Modify: `pyproject.toml`

**Step 1: pyproject.toml um CLI-Dependencies und Entry-Point erweitern**

```toml
[project]
name = "way2agi"
version = "1.0.0-alpha"
description = "Cognitive AI Agent — Terminal Application"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.80",
    "httpx>=0.27",
    "rich>=13.0",
    "click>=8.0",
    "elias-memory>=0.1",
]

[project.scripts]
way2agi = "cli.__main__:main"

[project.optional-dependencies]
memory-server = ["fastapi>=0.115", "uvicorn>=0.34"]
orchestrator = ["numpy>=1.26", "sqlite-vec>=0.1", "rank-bm25>=0.2"]
dev = ["pytest>=8.0", "pytest-cov>=4.0", "pytest-asyncio>=0.24"]
```

**Step 2: Entry-Point erstellen**

`cli/__main__.py`:
```python
"""Way2AGI CLI Entry-Point."""
import click

@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Way2AGI — Dein persoenlicher KI-Agent."""
    if ctx.invoked_subcommand is None:
        from cli.app import Way2AGIApp
        app = Way2AGIApp()
        app.run()

@main.command()
def chat():
    """Direkt in den Chat-Modus."""
    from cli.app import Way2AGIApp
    app = Way2AGIApp(start_screen="chat")
    app.run()

@main.command()
def doctor():
    """Systemdiagnose ausfuehren."""
    from cli.app import Way2AGIApp
    app = Way2AGIApp(start_screen="diagnostics")
    app.run()

if __name__ == "__main__":
    main()
```

**Step 3: Minimale Textual App**

`cli/__init__.py`: leer

`cli/app.py`:
```python
"""Way2AGI Textual Application."""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static

class Way2AGIApp(App):
    """Way2AGI Terminal Application."""

    TITLE = "Way2AGI"
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("q", "quit", "Beenden"),
    ]

    def __init__(self, start_screen: str = "dashboard"):
        super().__init__()
        self._start_screen = start_screen

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Way2AGI v1.0 — Loading...")
        yield Footer()
```

**Step 4: Testen ob Entry-Point funktioniert**

Run: `cd /data/data/com.termux/files/home/repos/Way2AGI && python -m cli --help`
Expected: Click help output mit "chat" und "doctor" subcommands

**Step 5: Commit**

```bash
git add cli/ pyproject.toml
git commit -m "feat: CLI skeleton with click entry-point and textual app shell"
```

---

### Task 2: Config Management

**Files:**
- Create: `cli/config.py`
- Create: `cli/tests/test_config.py`

**Step 1: Test schreiben**

```python
# cli/tests/test_config.py
import json
import tempfile
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

def test_provider_models():
    cfg = Way2AGIConfig._defaults()
    models = cfg["providers"]["openrouter"]["models"]
    assert "qwen/qwen3-coder" in models
    assert "step-flash" in str(models)
```

**Step 2: Run test — should fail**

Run: `pytest cli/tests/test_config.py -v`
Expected: FAIL (module not found)

**Step 3: Implementierung**

```python
# cli/config.py
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
```

**Step 4: Tests ausfuehren**

Run: `pytest cli/tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/config.py cli/tests/
git commit -m "feat: config manager with free-first defaults and dot-notation access"
```

---

### Task 3: LLM Client (Unified, OpenAI-kompatibel)

**Files:**
- Create: `cli/llm_client.py`
- Create: `cli/tests/test_llm_client.py`

**Step 1: Test schreiben**

```python
# cli/tests/test_llm_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from cli.llm_client import LLMClient

@pytest.mark.asyncio
async def test_build_headers_openrouter():
    client = LLMClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        provider="openrouter",
    )
    headers = client._build_headers()
    assert headers["Authorization"] == "Bearer test-key"
    assert "HTTP-Referer" in headers

@pytest.mark.asyncio
async def test_build_headers_anthropic():
    client = LLMClient(
        base_url="https://api.anthropic.com/v1",
        api_key="test-key",
        provider="anthropic",
    )
    headers = client._build_headers()
    assert headers["x-api-key"] == "test-key"
    assert "anthropic-version" in headers

def test_build_payload():
    client = LLMClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="",
        provider="openrouter",
    )
    payload = client._build_payload(
        model="qwen/qwen3-coder",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert payload["model"] == "qwen/qwen3-coder"
    assert payload["stream"] is True
    assert payload["messages"][0]["content"] == "hi"
```

**Step 2: Run test — should fail**

Run: `pytest cli/tests/test_llm_client.py -v`
Expected: FAIL

**Step 3: Implementierung**

```python
# cli/llm_client.py
"""Unified LLM Client — OpenAI-kompatibles Interface fuer alle Provider."""
from __future__ import annotations

from typing import AsyncIterator

import httpx


class LLMClient:
    """Async LLM client supporting OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        provider: str = "openrouter",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider = provider
        self.timeout = timeout

    def _build_headers(self) -> dict[str, str]:
        if self.provider == "anthropic":
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/Wittmann1988/Way2AGI"
            headers["X-Title"] = "Way2AGI"
        return headers

    def _build_payload(
        self,
        model: str,
        messages: list[dict],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return payload

    def _chat_endpoint(self) -> str:
        if self.provider == "anthropic":
            return f"{self.base_url}/messages"
        return f"{self.base_url}/chat/completions"

    async def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Non-streaming chat completion. Returns full response text."""
        payload = self._build_payload(model, messages, stream=False,
                                      temperature=temperature, max_tokens=max_tokens)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self._chat_endpoint(),
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return self._extract_text(data)

    async def stream(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion. Yields text chunks."""
        payload = self._build_payload(model, messages, stream=True,
                                      temperature=temperature, max_tokens=max_tokens)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self._chat_endpoint(),
                headers=self._build_headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    import json
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    text = self._extract_stream_chunk(obj)
                    if text:
                        yield text

    def _extract_text(self, data: dict) -> str:
        # Anthropic format
        if "content" in data and isinstance(data["content"], list):
            return "".join(
                block.get("text", "") for block in data["content"]
                if block.get("type") == "text"
            )
        # OpenAI format
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def _extract_stream_chunk(self, data: dict) -> str:
        # OpenAI SSE format
        choices = data.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            return delta.get("content", "")
        return ""
```

**Step 4: Tests ausfuehren**

Run: `pytest cli/tests/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/llm_client.py cli/tests/test_llm_client.py
git commit -m "feat: unified LLM client with streaming for all OpenAI-compatible providers"
```

---

### Task 4: Header Widget + Dashboard Screen

**Files:**
- Create: `cli/widgets/__init__.py`
- Create: `cli/widgets/header.py`
- Create: `cli/widgets/status.py`
- Create: `cli/screens/__init__.py`
- Create: `cli/screens/dashboard.py`
- Create: `cli/app.tcss`
- Modify: `cli/app.py`

**Step 1: Header Widget (Banner + Beschreibungstext)**

```python
# cli/widgets/header.py
"""Way2AGI Banner and description widget."""
from textual.widgets import Static

BANNER = r"""
 ╦ ╦┌─┐┬ ┬┌─┐╔═╗╔═╗╦
 ║║║├─┤└┬┘┌─┘╠═╣║ ╦║
 ╚╩╝┴ ┴ ┴ └─┘╩ ╩╚═╝╩
""".strip()

DESCRIPTION = """\
Dein persoenlicher KI-Agent der mit dir waechst.
Way2AGI verbindet freie & lokale Modelle mit echtem
Gedaechtnis und trainiert sich selbst — aus deiner Nutzung, auf deinem PC.

Anders als Chatbots hat Way2AGI einen kognitiven Kern:
Aufmerksamkeitssystem, Selbstbeobachtung und Verbesserung,
Bewusstseinsentwicklung — und Antriebe wie Neugier und
Kompetenzstreben die sein Handeln lenken — und ein
persistentes, aeusserst effizientes Gedaechtnis.

Der Orchestrator waehlt automatisch das beste Modell fuer jede Aufgabe:
schnelle Modelle fuer einfache Fragen, starke fuer komplexe Probleme,
mehrere gleichzeitig fuer kritische Entscheidungen.
586 Modelle, 9 Provider — ein Agent der sie alle intelligent kombiniert.

Kein Abo noetig. Keine Cloud. Deine Daten.
Freie Modelle · Lokales Memory · Selbsttraining · Kognitiver Kern · Multi-Modell Orchestrierung"""


class Way2AGIHeader(Static):
    """Banner + description displayed at top of dashboard."""

    def __init__(self) -> None:
        super().__init__(f"{BANNER}\n\n{DESCRIPTION}")
        self.add_class("way2agi-header")
```

**Step 2: Status Widget**

```python
# cli/widgets/status.py
"""Status panel showing current provider, memory, model info."""
from textual.widgets import Static
from cli.config import Way2AGIConfig


class StatusPanel(Static):
    """Left-side status display."""

    def __init__(self, config: Way2AGIConfig) -> None:
        self.config = config
        super().__init__(self._render())
        self.add_class("status-panel")

    def _render(self) -> str:
        return (
            f"Provider:      {self.config.provider}\n"
            f"Model:         {self.config.model}\n"
            f"Memory:        {'ON' if self.config.get('memory.enabled') else 'OFF'}\n"
            f"Cognitive:     OFF\n"
            f"Selbstmodelle: 0"
        )

    def refresh_status(self) -> None:
        self.update(self._render())
```

**Step 3: Dashboard Screen**

```python
# cli/screens/dashboard.py
"""Dashboard — Start screen with header, status, and quick actions."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.containers import Horizontal

from cli.widgets.header import Way2AGIHeader
from cli.widgets.status import StatusPanel
from cli.config import Way2AGIConfig

ACTIONS_TEXT = """\
[C] Chat starten
[S] Settings
[M] Memory Browser
[T] Training Pipeline
[D] Diagnostics
[Q] Beenden"""


class DashboardScreen(Screen):
    """Main dashboard with status and quick actions."""

    BINDINGS = [
        ("c", "open_chat", "Chat"),
        ("s", "open_settings", "Settings"),
        ("m", "open_memory", "Memory"),
        ("d", "open_diagnostics", "Diagnostics"),
        ("q", "quit", "Beenden"),
    ]

    def __init__(self, config: Way2AGIConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Way2AGIHeader()
        with Horizontal(id="dashboard-panels"):
            yield StatusPanel(self.config)
            yield Static(ACTIONS_TEXT, classes="actions-panel")
        yield Footer()

    def action_open_chat(self) -> None:
        self.app.push_screen("chat")

    def action_open_settings(self) -> None:
        self.app.push_screen("settings")

    def action_open_memory(self) -> None:
        self.app.push_screen("memory")

    def action_open_diagnostics(self) -> None:
        self.app.push_screen("diagnostics")

    def action_quit(self) -> None:
        self.app.exit()
```

**Step 4: CSS-Datei**

```css
/* cli/app.tcss */
.way2agi-header {
    padding: 1 2;
    color: $accent;
    text-align: center;
}

#dashboard-panels {
    height: auto;
    padding: 1 2;
}

.status-panel {
    width: 1fr;
    padding: 1 2;
    border: solid $primary;
}

.actions-panel {
    width: 1fr;
    padding: 1 2;
    border: solid $secondary;
}
```

**Step 5: App aktualisieren**

`cli/app.py` erweitern:
```python
"""Way2AGI Textual Application."""
from textual.app import App
from cli.config import Way2AGIConfig
from cli.screens.dashboard import DashboardScreen


class Way2AGIApp(App):
    """Way2AGI Terminal Application."""

    TITLE = "Way2AGI"
    CSS_PATH = "app.tcss"

    def __init__(self, start_screen: str = "dashboard"):
        super().__init__()
        self._start_screen = start_screen
        self.config = Way2AGIConfig()

    def on_mount(self) -> None:
        self.install_screen(DashboardScreen(self.config), name="dashboard")
        self.push_screen("dashboard")
```

**Step 6: Manuell testen**

Run: `cd /data/data/com.termux/files/home/repos/Way2AGI && python -m cli`
Expected: Dashboard mit Banner, Beschreibungstext, Status-Panel und Quick Actions

**Step 7: Commit**

```bash
git add cli/widgets/ cli/screens/ cli/app.py cli/app.tcss
git commit -m "feat: dashboard screen with Way2AGI header, status panel, and quick actions"
```

---

### Task 5: Settings Screen

**Files:**
- Create: `cli/screens/settings.py`

**Step 1: Implementierung**

```python
# cli/screens/settings.py
"""Settings screen — Provider, API-Key, Model configuration."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Footer, Static, Select, Input, Button, Label,
)
from textual.containers import Vertical, Horizontal

from cli.config import Way2AGIConfig

PROVIDERS = [
    ("OpenRouter (Gratis-Modelle)", "openrouter"),
    ("Groq (Ultra-Schnell)", "groq"),
    ("Ollama (Lokal)", "ollama"),
    ("Anthropic (Claude)", "anthropic"),
    ("OpenAI (GPT)", "openai"),
    ("Google (Gemini)", "google"),
    ("Custom (OpenAI-kompatibel)", "custom"),
]


class SettingsScreen(Screen):
    """Provider and model configuration."""

    BINDINGS = [("escape", "go_back", "Zurueck")]

    def __init__(self, config: Way2AGIConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Static("Einstellungen", classes="screen-title")
        with Vertical(id="settings-form"):
            yield Label("Provider")
            yield Select(
                PROVIDERS,
                value=self.config.provider,
                id="provider-select",
            )
            yield Label("API Key")
            yield Input(
                value=self.config.provider_config.get("api_key", ""),
                password=True,
                placeholder="API Key eingeben (leer = Env-Variable)",
                id="api-key-input",
            )
            yield Label("Modell")
            yield Select(
                self._model_options(),
                value=self.config.model,
                id="model-select",
            )
            yield Static("")
            yield Label("Custom Provider (OpenAI-kompatibel)")
            yield Input(
                value=self.config.get("providers.custom.base_url", ""),
                placeholder="https://api.example.com/v1",
                id="custom-url-input",
            )
            with Horizontal():
                yield Button("Speichern", variant="primary", id="save-btn")
                yield Button("Zurueck", id="back-btn")
        yield Footer()

    def _model_options(self) -> list[tuple[str, str]]:
        models = self.config.provider_config.get("models", [])
        return [(m, m) for m in models] if models else [("(keine)", "")]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            self.config.set("provider", event.value)
            model_select = self.query_one("#model-select", Select)
            model_select._options = self._model_options()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            api_input = self.query_one("#api-key-input", Input)
            self.config.set(
                f"providers.{self.config.provider}.api_key",
                api_input.value,
            )
            custom_url = self.query_one("#custom-url-input", Input)
            if custom_url.value:
                self.config.set("providers.custom.base_url", custom_url.value)
            model_select = self.query_one("#model-select", Select)
            if model_select.value:
                self.config.set("model", model_select.value)
            self.config.save()
            self.notify("Einstellungen gespeichert!")
        elif event.button.id == "back-btn":
            self.action_go_back()

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

**Step 2: In App registrieren**

In `cli/app.py` -> `on_mount()` hinzufuegen:
```python
from cli.screens.settings import SettingsScreen
self.install_screen(SettingsScreen(self.config), name="settings")
```

**Step 3: Manuell testen**

Run: `python -m cli` -> [S] druecken
Expected: Settings-Screen mit Provider-Dropdown, API-Key-Feld, Model-Auswahl

**Step 4: Commit**

```bash
git add cli/screens/settings.py cli/app.py
git commit -m "feat: settings screen with provider selection, API key, model config"
```

---

### Task 6: Chat Screen mit Streaming

**Files:**
- Create: `cli/screens/chat.py`
- Create: `cli/widgets/chat_log.py`

**Step 1: Chat Log Widget**

```python
# cli/widgets/chat_log.py
"""Scrollable chat log widget."""
from textual.widgets import RichLog


class ChatLog(RichLog):
    """Scrollable chat message display."""

    def add_user_message(self, text: str) -> None:
        self.write(f"[bold cyan]User:[/] {text}")

    def add_assistant_chunk(self, text: str) -> None:
        """Append streaming chunk (no newline)."""
        self.write(text, expand=True, scroll_end=True)

    def start_assistant_message(self) -> None:
        self.write("[bold green]Assistant:[/] ", expand=True)

    def end_assistant_message(self, token_count: int = 0) -> None:
        info = f" [Tokens: {token_count}]" if token_count else ""
        self.write(f"\n[dim]{info}[/]")

    def add_system_message(self, text: str) -> None:
        self.write(f"[dim italic]{text}[/]")
```

**Step 2: Chat Screen**

```python
# cli/screens/chat.py
"""Chat screen with streaming LLM responses and memory integration."""
from __future__ import annotations

import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, Input
from textual.containers import Vertical

from cli.config import Way2AGIConfig
from cli.llm_client import LLMClient
from cli.widgets.chat_log import ChatLog


class ChatScreen(Screen):
    """Interactive chat with LLM."""

    BINDINGS = [
        ("escape", "go_back", "Dashboard"),
        ("f3", "switch_model", "Modell"),
    ]

    def __init__(self, config: Way2AGIConfig) -> None:
        super().__init__()
        self.config = config
        self.messages: list[dict[str, str]] = []
        self._client: LLMClient | None = None

    def compose(self) -> ComposeResult:
        model = self.config.model
        provider = self.config.provider
        yield Static(
            f"Way2AGI Chat — {model} ({provider}) — [Esc] Dashboard",
            classes="chat-header",
        )
        yield ChatLog(id="chat-log", wrap=True, highlight=True)
        yield Input(placeholder="Nachricht eingeben...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", ChatLog)
        log.add_system_message("Hallo! Wie kann ich helfen?")
        self.query_one("#chat-input").focus()

    def _get_client(self) -> LLMClient:
        if self._client is None:
            pcfg = self.config.provider_config
            self._client = LLMClient(
                base_url=pcfg.get("base_url", ""),
                api_key=pcfg.get("api_key", ""),
                provider=self.config.provider,
            )
        return self._client

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        event.input.clear()
        log = self.query_one("#chat-log", ChatLog)

        # Slash commands
        if text.startswith("/"):
            await self._handle_command(text, log)
            return

        # User message
        log.add_user_message(text)
        self.messages.append({"role": "user", "content": text})

        # Memory recall (if enabled)
        context = await self._recall_memory(text)
        if context:
            log.add_system_message(f"[Memory: {len(context)} relevante Erinnerungen]")

        # Stream response
        log.start_assistant_message()
        client = self._get_client()
        full_response = ""
        try:
            async for chunk in client.stream(
                model=self.config.model,
                messages=self._build_messages(context),
            ):
                log.add_assistant_chunk(chunk)
                full_response += chunk
        except Exception as e:
            log.add_system_message(f"Fehler: {e}")
            return

        log.end_assistant_message()
        self.messages.append({"role": "assistant", "content": full_response})

        # Memory store (if enabled)
        await self._store_memory(text, full_response)

    def _build_messages(self, context: str | None) -> list[dict]:
        msgs = []
        system = "Du bist Way2AGI, ein kognitiver KI-Agent."
        if context:
            system += f"\n\nRelevanter Kontext aus dem Gedaechtnis:\n{context}"
        msgs.append({"role": "system", "content": system})
        msgs.extend(self.messages[-20:])  # Last 20 messages
        return msgs

    async def _recall_memory(self, query: str) -> str | None:
        if not self.config.get("memory.enabled") or not self.config.get("memory.auto_recall"):
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    "http://localhost:5000/memory/query",
                    json={"query": query, "top_k": self.config.get("memory.recall_top_k", 3), "memory_type": "all"},
                )
                if resp.status_code == 200:
                    results = resp.json()
                    if results:
                        return "\n".join(r["content"] for r in results)
        except Exception:
            pass
        return None

    async def _store_memory(self, user_msg: str, assistant_msg: str) -> None:
        if not self.config.get("memory.enabled") or not self.config.get("memory.auto_store"):
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    "http://localhost:5000/memory/store",
                    json={
                        "content": f"User: {user_msg}\nAssistant: {assistant_msg[:500]}",
                        "memory_type": "episodic",
                        "importance": 0.5,
                    },
                )
        except Exception:
            pass

    async def _handle_command(self, cmd: str, log: ChatLog) -> None:
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "/clear":
            self.messages.clear()
            log.clear()
            log.add_system_message("Chat geloescht.")
        elif command == "/model":
            if arg:
                self.config.set("model", arg)
                self._client = None
                log.add_system_message(f"Modell gewechselt: {arg}")
            else:
                log.add_system_message(f"Aktuell: {self.config.model}")
        elif command == "/memory":
            if arg.startswith("search "):
                query = arg[7:]
                context = await self._recall_memory(query)
                log.add_system_message(context or "Keine Erinnerungen gefunden.")
            else:
                log.add_system_message("Befehle: /memory search <query>")
        else:
            log.add_system_message(f"Unbekannt: {command}. Verfuegbar: /clear, /model, /memory")

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_switch_model(self) -> None:
        models = self.config.provider_config.get("models", [])
        if not models:
            return
        current = self.config.model
        idx = models.index(current) if current in models else -1
        next_model = models[(idx + 1) % len(models)]
        self.config.set("model", next_model)
        self._client = None
        log = self.query_one("#chat-log", ChatLog)
        log.add_system_message(f"Modell: {next_model}")
```

**Step 3: In App registrieren + CSS erweitern**

In `cli/app.py` -> `on_mount()`:
```python
from cli.screens.chat import ChatScreen
self.install_screen(ChatScreen(self.config), name="chat")
```

In `cli/app.tcss` anfuegen:
```css
.chat-header {
    dock: top;
    padding: 0 2;
    background: $primary;
    color: $text;
}

#chat-log {
    height: 1fr;
    padding: 0 1;
}

#chat-input {
    dock: bottom;
}
```

**Step 4: Manuell testen**

Run: `python -m cli` -> [C] -> Nachricht eingeben
Expected: Streaming-Antwort vom konfigurierten Provider

**Step 5: Commit**

```bash
git add cli/screens/chat.py cli/widgets/chat_log.py cli/app.py cli/app.tcss
git commit -m "feat: chat screen with streaming responses, memory integration, slash commands"
```

---

### Task 7: Memory Browser Screen

**Files:**
- Create: `cli/screens/memory_browser.py`

**Step 1: Implementierung**

```python
# cli/screens/memory_browser.py
"""Memory Browser — Search, browse, and manage memories."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, Input, DataTable
from textual.containers import Vertical

from cli.config import Way2AGIConfig


class MemoryBrowserScreen(Screen):
    """Browse and search stored memories."""

    BINDINGS = [("escape", "go_back", "Dashboard")]

    def __init__(self, config: Way2AGIConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Static("Memory Browser", classes="screen-title")
        yield Input(placeholder="Suche in Erinnerungen...", id="memory-search")
        yield DataTable(id="memory-table")
        yield Static("", id="memory-stats")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#memory-table", DataTable)
        table.add_columns("Typ", "Inhalt", "Wichtigkeit", "Erstellt")
        await self._load_stats()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        await self._search(query)

    async def _search(self, query: str) -> None:
        table = self.query_one("#memory-table", DataTable)
        table.clear()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "http://localhost:5000/memory/query",
                    json={"query": query, "top_k": 20, "memory_type": "all"},
                )
                if resp.status_code == 200:
                    results = resp.json()
                    for r in results:
                        table.add_row(
                            r.get("type", "?"),
                            r.get("content", "")[:80],
                            f"{r.get('importance', 0):.2f}",
                            r.get("created_at", "")[:10],
                        )
                    stats = self.query_one("#memory-stats", Static)
                    stats.update(f"{len(results)} Ergebnis(se) gefunden")
        except Exception as e:
            stats = self.query_one("#memory-stats", Static)
            stats.update(f"Memory Server nicht erreichbar: {e}")

    async def _load_stats(self) -> None:
        stats = self.query_one("#memory-stats", Static)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("http://localhost:5000/health")
                if resp.status_code == 200:
                    data = resp.json()
                    total = data.get("total_memories", 0)
                    stores = data.get("stores", {})
                    info = " | ".join(f"{k}: {v}" for k, v in stores.items())
                    stats.update(f"Gesamt: {total} Erinnerungen | {info}")
                    return
        except Exception:
            pass
        stats.update("Memory Server nicht erreichbar. Starten mit: python -m memory.src.server")

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

**Step 2: In App registrieren**

In `cli/app.py` -> `on_mount()`:
```python
from cli.screens.memory_browser import MemoryBrowserScreen
self.install_screen(MemoryBrowserScreen(self.config), name="memory")
```

**Step 3: Commit**

```bash
git add cli/screens/memory_browser.py cli/app.py
git commit -m "feat: memory browser screen with search and stats"
```

---

### Task 8: Diagnostics Screen

**Files:**
- Create: `cli/screens/diagnostics.py`

**Step 1: Implementierung**

```python
# cli/screens/diagnostics.py
"""Diagnostics screen — System health checks."""
from __future__ import annotations

import shutil
import sys
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, RichLog, Button

from cli.config import Way2AGIConfig


class DiagnosticsScreen(Screen):
    """Run system diagnostics."""

    BINDINGS = [("escape", "go_back", "Dashboard")]

    def __init__(self, config: Way2AGIConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Static("Way2AGI Diagnostics", classes="screen-title")
        yield RichLog(id="diag-log", wrap=True)
        yield Button("Erneut pruefen", id="rerun-btn")
        yield Footer()

    async def on_mount(self) -> None:
        await self._run_checks()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rerun-btn":
            log = self.query_one("#diag-log", RichLog)
            log.clear()
            await self._run_checks()

    async def _run_checks(self) -> None:
        log = self.query_one("#diag-log", RichLog)
        errors = 0

        # Python
        v = sys.version.split()[0]
        major = int(v.split(".")[0])
        ok = major >= 3 and int(v.split(".")[1]) >= 11
        log.write(f"{'[OK]' if ok else '[FAIL]'} Python: {v}")
        if not ok:
            errors += 1

        # Config
        if self.config.path.exists():
            log.write(f"[OK]   Config: {self.config.path}")
        else:
            log.write(f"[WARN] Config: nicht gefunden — wird beim Speichern erstellt")

        # Node.js (optional)
        node = shutil.which("node")
        if node:
            log.write(f"[OK]   Node.js: {node}")
        else:
            log.write("[INFO] Node.js: nicht gefunden (optional, fuer Cognitive Core)")

        # Memory Server
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get("http://localhost:5000/health")
                if resp.status_code == 200:
                    data = resp.json()
                    log.write(f"[OK]   Memory Server: v{data.get('version', '?')} ({data.get('total_memories', 0)} Erinnerungen)")
                else:
                    log.write(f"[FAIL] Memory Server: HTTP {resp.status_code}")
                    errors += 1
        except Exception:
            log.write("[WARN] Memory Server: nicht erreichbar (Memory-Features deaktiviert)")

        # Provider
        provider = self.config.provider
        key = self.config.provider_config.get("api_key", "")
        if provider in ("openrouter", "groq") and not key:
            log.write(f"[WARN] {provider}: Kein API-Key (einige Gratis-Modelle funktionieren trotzdem)")
        elif key:
            log.write(f"[OK]   Provider: {provider} (Key konfiguriert)")
        else:
            log.write(f"[WARN] Provider: {provider} (kein API-Key)")

        # Ollama
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    names = [m["name"] for m in models[:5]]
                    log.write(f"[OK]   Ollama: {len(models)} lokale Modelle ({', '.join(names)})")
                else:
                    log.write("[WARN] Ollama: laeuft aber keine Modelle")
        except Exception:
            log.write("[INFO] Ollama: nicht erreichbar (lokale Modelle nicht verfuegbar)")

        # Summary
        log.write("")
        if errors == 0:
            log.write("[bold green]Alle kritischen Checks bestanden![/]")
        else:
            log.write(f"[bold red]{errors} Problem(e) gefunden.[/]")

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

**Step 2: In App registrieren**

In `cli/app.py` -> `on_mount()`:
```python
from cli.screens.diagnostics import DiagnosticsScreen
self.install_screen(DiagnosticsScreen(self.config), name="diagnostics")
```

**Step 3: Commit**

```bash
git add cli/screens/diagnostics.py cli/app.py
git commit -m "feat: diagnostics screen with health checks for all components"
```

---

### Task 9: Bootstrap + First-Run Experience

**Files:**
- Create: `cli/bootstrap.py`
- Modify: `cli/app.py`

**Step 1: Bootstrap-Modul**

```python
# cli/bootstrap.py
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
```

**Step 2: App-Integration — bei First-Run direkt Settings oeffnen**

In `cli/app.py` -> `on_mount()` am Ende:
```python
from cli.bootstrap import is_first_run, ensure_data_dir, run_first_time_setup
ensure_data_dir()
if is_first_run():
    run_first_time_setup(self.config)
    self.push_screen("settings")
```

**Step 3: Commit**

```bash
git add cli/bootstrap.py cli/app.py
git commit -m "feat: first-run bootstrap creates config and opens settings"
```

---

### Task 10: Integration + Finaler Test

**Files:**
- Modify: `cli/app.py` (finale Version)
- Create: `cli/screens/__init__.py`
- Create: `cli/widgets/__init__.py`
- Create: `cli/tests/__init__.py`

**Step 1: Finale app.py mit allen Screens**

```python
# cli/app.py
"""Way2AGI Textual Application."""
from textual.app import App
from cli.config import Way2AGIConfig
from cli.bootstrap import is_first_run, ensure_data_dir, run_first_time_setup


class Way2AGIApp(App):
    """Way2AGI Terminal Application."""

    TITLE = "Way2AGI"
    CSS_PATH = "app.tcss"

    def __init__(self, start_screen: str = "dashboard"):
        super().__init__()
        self._start_screen = start_screen
        self.config = Way2AGIConfig()

    def on_mount(self) -> None:
        from cli.screens.dashboard import DashboardScreen
        from cli.screens.chat import ChatScreen
        from cli.screens.settings import SettingsScreen
        from cli.screens.memory_browser import MemoryBrowserScreen
        from cli.screens.diagnostics import DiagnosticsScreen

        self.install_screen(DashboardScreen(self.config), name="dashboard")
        self.install_screen(ChatScreen(self.config), name="chat")
        self.install_screen(SettingsScreen(self.config), name="settings")
        self.install_screen(MemoryBrowserScreen(self.config), name="memory")
        self.install_screen(DiagnosticsScreen(self.config), name="diagnostics")

        ensure_data_dir()
        if is_first_run():
            run_first_time_setup(self.config)

        self.push_screen(self._start_screen)
```

**Step 2: __init__.py Dateien erstellen**

Alle leer: `cli/screens/__init__.py`, `cli/widgets/__init__.py`, `cli/tests/__init__.py`

**Step 3: Alle Tests ausfuehren**

Run: `pytest cli/tests/ -v`
Expected: Alle Tests PASS

**Step 4: Manueller End-to-End Test**

Run: `python -m cli`
Pruefen:
1. Dashboard erscheint mit Banner + Beschreibung + Status
2. [C] oeffnet Chat, Nachricht senden funktioniert mit Streaming
3. [Esc] zurueck zum Dashboard
4. [S] oeffnet Settings, Provider wechseln + speichern
5. [M] oeffnet Memory Browser (zeigt Fehler wenn Server nicht laeuft)
6. [D] oeffnet Diagnostics mit allen Checks

**Step 5: Commit**

```bash
git add cli/
git commit -m "feat: Way2AGI Terminal App v1.0 MVP — Dashboard, Chat, Settings, Memory, Diagnostics"
```

---

## Zusammenfassung

| Task | Beschreibung | Dateien |
|------|-------------|---------|
| 1 | Skeleton + Entry-Point | `cli/__main__.py`, `cli/app.py`, `pyproject.toml` |
| 2 | Config Management | `cli/config.py` + Tests |
| 3 | LLM Client (Streaming) | `cli/llm_client.py` + Tests |
| 4 | Header + Dashboard | `cli/widgets/`, `cli/screens/dashboard.py`, `app.tcss` |
| 5 | Settings Screen | `cli/screens/settings.py` |
| 6 | Chat Screen | `cli/screens/chat.py`, `cli/widgets/chat_log.py` |
| 7 | Memory Browser | `cli/screens/memory_browser.py` |
| 8 | Diagnostics | `cli/screens/diagnostics.py` |
| 9 | Bootstrap | `cli/bootstrap.py` |
| 10 | Integration + Test | Finale `cli/app.py` |

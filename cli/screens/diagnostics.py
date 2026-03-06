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
        minor = int(v.split(".")[1])
        ok = major >= 3 and minor >= 11
        log.write(f"{'[OK]' if ok else '[FAIL]'} Python: {v}")
        if not ok:
            errors += 1

        # Config
        if self.config.path.exists():
            log.write(f"[OK]   Config: {self.config.path}")
        else:
            log.write("[WARN] Config: nicht gefunden — wird beim Speichern erstellt")

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

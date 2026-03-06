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

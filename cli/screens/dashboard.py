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

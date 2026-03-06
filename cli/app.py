"""Way2AGI Textual Application."""
from textual.app import App
from cli.config import Way2AGIConfig
from cli.bootstrap import ensure_data_dir, is_first_run, run_first_time_setup


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

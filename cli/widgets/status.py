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

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

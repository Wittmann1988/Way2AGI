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
            # Update model list for new provider
            model_select = self.query_one("#model-select", Select)
            new_options = self._model_options()
            model_select.set_options(new_options)

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
            if model_select.value and model_select.value != Select.BLANK:
                self.config.set("model", str(model_select.value))
            self.config.save()
            self.notify("Einstellungen gespeichert!")
        elif event.button.id == "back-btn":
            self.action_go_back()

    def action_go_back(self) -> None:
        self.app.pop_screen()

"""Chat screen with streaming LLM responses, memory, tool-use, and feedback."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, Input

from cli.config import Way2AGIConfig
from cli.llm_client import LLMClient
from cli.widgets.chat_log import ChatLog
from cli.tools.setup import create_default_registry
from cli.tools.parser import parse_tool_calls
from cli.feedback import FeedbackStore


class ChatScreen(Screen):
    """Interactive chat with LLM, tool-use loop, and RLHF feedback."""

    BINDINGS = [
        ("escape", "go_back", "Dashboard"),
        ("f3", "switch_model", "Modell"),
        ("+", "thumbs_up", "Gut"),
        ("-", "thumbs_down", "Schlecht"),
    ]

    def __init__(self, config: Way2AGIConfig) -> None:
        super().__init__()
        self.config = config
        self.messages: list[dict[str, str]] = []
        self._client: LLMClient | None = None
        self._tools = create_default_registry()
        self._feedback = FeedbackStore()
        self._last_exchange: tuple[str, str] | None = None

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
            log.add_system_message("[Memory: relevante Erinnerungen gefunden]")

        # Tool-use loop (max 5 iterations)
        full_response = ""
        for _iteration in range(5):
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

            # Check for tool calls
            tool_calls = parse_tool_calls(full_response)
            if not tool_calls:
                self.messages.append({"role": "assistant", "content": full_response})
                break

            # Execute tools and feed results back
            self.messages.append({"role": "assistant", "content": full_response})
            for tc in tool_calls:
                result = self._tools.dispatch(tc.name, tc.args)
                status = "OK" if result.success else "FEHLER"
                tool_output = f"[Tool {tc.name}: {status}]\n{result.output[:2000]}"
                log.add_system_message(tool_output)
                self.messages.append({
                    "role": "user",
                    "content": f"Tool-Ergebnis fuer {tc.name}:\n{result.output[:2000]}",
                })

            context = None  # Don't re-inject memory context

        self._last_exchange = (text, full_response)

        # Memory store (if enabled)
        await self._store_memory(text, full_response)

    def _build_messages(self, context: str | None) -> list[dict]:
        msgs = []
        system = "Du bist Way2AGI, ein kognitiver KI-Agent."
        system += "\n\n" + self._tools.tool_prompt()
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
                    json={
                        "query": query,
                        "top_k": self.config.get("memory.recall_top_k", 3),
                        "memory_type": "all",
                    },
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
        elif command == "/feedback":
            stats = self._feedback.stats()
            log.add_system_message(
                f"Feedback: {stats['total']} gesamt, "
                f"{stats['positive']} positiv, {stats['negative']} negativ"
            )
        else:
            log.add_system_message(
                f"Unbekannt: {command}. Verfuegbar: /clear, /model, /memory, /feedback"
            )

    def action_thumbs_up(self) -> None:
        if self._last_exchange:
            user, assistant = self._last_exchange
            self._feedback.record(user, assistant, rating=1, model=self.config.model)
            log = self.query_one("#chat-log", ChatLog)
            log.add_system_message("[+1 Feedback gespeichert]")

    def action_thumbs_down(self) -> None:
        if self._last_exchange:
            user, assistant = self._last_exchange
            self._feedback.record(user, assistant, rating=-1, model=self.config.model)
            log = self.query_one("#chat-log", ChatLog)
            log.add_system_message("[-1 Feedback gespeichert]")

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

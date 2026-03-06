from __future__ import annotations
import shlex
import subprocess
from cli.tools.registry import Tool, ToolResult

_SHELL_OPERATORS = ["|", ";", "&&", "||", "`", "$(", "${"]

def make_shell_tool(allowed_commands: list[str] | None = None, timeout: int = 30) -> Tool:
    if allowed_commands is None:
        allowed_commands = ["echo", "ls", "cat", "head", "tail", "wc", "find", "grep",
            "python", "python3", "pip", "node", "npm", "git", "date", "whoami", "uname", "df", "du", "pwd"]

    def handler(command: str) -> ToolResult:
        if not command.strip():
            return ToolResult(success=False, output="Leerer Befehl")
        for op in _SHELL_OPERATORS:
            if op in command:
                return ToolResult(success=False, output=f"Shell-Operator nicht erlaubt: {op}")
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return ToolResult(success=False, output=f"Parsing-Fehler: {e}")
        base_cmd = parts[0] if parts else ""
        if base_cmd not in allowed_commands:
            return ToolResult(success=False, output=f"Befehl nicht erlaubt: {base_cmd}. Erlaubt: {', '.join(allowed_commands)}")
        try:
            proc = subprocess.run(parts, capture_output=True, text=True, timeout=timeout)
            output = proc.stdout
            if proc.stderr:
                output += f"\n[stderr] {proc.stderr}"
            if len(output) > 50_000:
                output = output[:50_000] + "\n... (gekuerzt)"
            return ToolResult(success=proc.returncode == 0, output=output)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output=f"Timeout nach {timeout}s")
        except FileNotFoundError:
            return ToolResult(success=False, output=f"Befehl nicht gefunden: {base_cmd}")
        except Exception as e:
            return ToolResult(success=False, output=f"Fehler: {e}")

    return Tool(
        name="shell_exec",
        description=f"Shell-Befehl ausfuehren (erlaubt: {', '.join(allowed_commands[:5])}...)",
        parameters={"command": "str"},
        handler=handler,
    )

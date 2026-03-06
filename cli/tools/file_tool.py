from __future__ import annotations
import os
from cli.tools.registry import Tool, ToolResult

def _is_path_allowed(path: str, allowed_dirs: list[str]) -> bool:
    resolved = os.path.realpath(path)
    for d in allowed_dirs:
        allowed = os.path.realpath(d)
        if resolved == allowed or resolved.startswith(allowed + os.sep):
            return True
    return False

def make_file_read_tool(allowed_dirs: list[str]) -> Tool:
    def handler(path: str) -> ToolResult:
        if not _is_path_allowed(path, allowed_dirs):
            return ToolResult(success=False, output=f"Pfad nicht erlaubt: {path}")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(100_000)
            return ToolResult(success=True, output=content)
        except FileNotFoundError:
            return ToolResult(success=False, output=f"Datei nicht gefunden: {path}")
        except Exception as e:
            return ToolResult(success=False, output=f"Fehler: {e}")
    return Tool(name="file_read", description="Datei lesen (max 100KB)", parameters={"path": "str"}, handler=handler)

def make_file_write_tool(allowed_dirs: list[str]) -> Tool:
    def handler(path: str, content: str) -> ToolResult:
        if not _is_path_allowed(path, allowed_dirs):
            return ToolResult(success=False, output=f"Pfad nicht erlaubt: {path}")
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Geschrieben: {path} ({len(content)} Bytes)")
        except Exception as e:
            return ToolResult(success=False, output=f"Fehler: {e}")
    return Tool(name="file_write", description="Datei schreiben", parameters={"path": "str", "content": "str"}, handler=handler)

from __future__ import annotations
import ipaddress
from urllib.parse import urlparse
from cli.tools.registry import Tool, ToolResult

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_ALLOWED_SCHEMES = {"http", "https"}

def _is_url_safe(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Ungueltige URL"
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False, f"Schema nicht erlaubt: {parsed.scheme}"
    host = parsed.hostname or ""
    if host in _BLOCKED_HOSTS:
        return False, f"Host blockiert: {host}"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_link_local or ip.is_loopback:
            return False, f"Private IP blockiert: {host}"
    except ValueError:
        pass
    return True, ""

def make_web_fetch_tool(timeout: int = 15) -> Tool:
    def handler(url: str) -> ToolResult:
        safe, reason = _is_url_safe(url)
        if not safe:
            return ToolResult(success=False, output=reason)
        try:
            import httpx
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Way2AGI/1.1"})
                resp.raise_for_status()
                return ToolResult(success=True, output=resp.text[:50_000])
        except Exception as e:
            return ToolResult(success=False, output=f"Fehler: {e}")
    return Tool(name="web_fetch", description="Webseite abrufen (GET, max 50KB Text)", parameters={"url": "str"}, handler=handler)

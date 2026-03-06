"""Parse text-based tool calls from LLM output.

Format: TOOL: name(key=value, key2=value2)
"""

import re
from dataclasses import dataclass, field


TOOL_PATTERN = re.compile(r"^TOOL:\s*(\w+)\(([^)]*)\)\s*$", re.MULTILINE)


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)
    prefix: str = ""


def _parse_args(raw: str) -> dict:
    """Split on commas, respect quoted strings, return dict."""
    raw = raw.strip()
    if not raw:
        return {}

    args = {}
    # Split respecting quoted strings
    parts = re.split(r',\s*(?=\w+=)', raw)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        # Remove surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        args[key] = value
    return args


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Parse all TOOL: calls from text, capturing prefix text before each."""
    results = []
    last_end = 0

    for match in TOOL_PATTERN.finditer(text):
        prefix = text[last_end:match.start()].rstrip("\n")
        name = match.group(1)
        raw_args = match.group(2)
        results.append(ToolCall(name=name, args=_parse_args(raw_args), prefix=prefix))
        last_end = match.end()

    return results

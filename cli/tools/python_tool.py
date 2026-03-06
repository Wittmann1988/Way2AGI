from __future__ import annotations
import io
import contextlib
import re
from cli.tools.registry import Tool, ToolResult

_BLOCKED_PATTERNS = [
    r"\bimport\b", r"\b__\w+__\b", r"\bexec\b", r"\beval\b", r"\bcompile\b",
    r"\bglobals\b", r"\blocals\b", r"\bgetattr\b", r"\bsetattr\b", r"\bdelattr\b",
    r"\bopen\b", r"\bbreakpoint\b", r"\binput\b",
]

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "chr": chr, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "hash": hash, "hex": hex, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len, "list": list,
    "map": map, "max": max, "min": min, "next": next, "oct": oct,
    "ord": ord, "pow": pow, "print": print, "range": range,
    "repr": repr, "reversed": reversed, "round": round, "set": set,
    "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "zip": zip,
}

def make_python_eval_tool(timeout: int = 5) -> Tool:
    def handler(code: str) -> ToolResult:
        for pattern in _BLOCKED_PATTERNS:
            if re.search(pattern, code):
                return ToolResult(success=False, output=f"Blockiert: Pattern '{pattern}' nicht erlaubt")
        stdout = io.StringIO()
        try:
            env = {"__builtins__": _SAFE_BUILTINS}
            with contextlib.redirect_stdout(stdout):
                try:
                    result = eval(code, env)
                    if result is not None:
                        print(repr(result), file=stdout)
                except SyntaxError:
                    exec(code, env)
            output = stdout.getvalue().strip()
            return ToolResult(success=True, output=output or "(kein Output)")
        except Exception as e:
            return ToolResult(success=False, output=f"Fehler: {type(e).__name__}: {e}")
    return Tool(name="python_eval", description="Python-Code ausfuehren (sandbox, kein import/open/exec)", parameters={"code": "str"}, handler=handler)

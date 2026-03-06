"""Default tool registration for Way2AGI CLI."""
from __future__ import annotations

import os
from cli.tools.registry import ToolRegistry
from cli.tools.file_tool import make_file_read_tool, make_file_write_tool
from cli.tools.shell_tool import make_shell_tool
from cli.tools.web_tool import make_web_fetch_tool
from cli.tools.memory_tool import make_memory_query_tool
from cli.tools.python_tool import make_python_eval_tool


def create_default_registry() -> ToolRegistry:
    """Create registry with all default tools."""
    reg = ToolRegistry()

    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".way2agi")
    allowed_dirs = [home, data_dir, "/tmp"]

    reg.register(make_file_read_tool(allowed_dirs=allowed_dirs))
    reg.register(make_file_write_tool(allowed_dirs=[data_dir, "/tmp"]))
    reg.register(make_shell_tool())
    reg.register(make_web_fetch_tool())
    reg.register(make_memory_query_tool())
    reg.register(make_python_eval_tool())

    return reg

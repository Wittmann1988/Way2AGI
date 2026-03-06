from cli.tools.shell_tool import make_shell_tool


def test_shell_allowed_command():
    tool = make_shell_tool()
    result = tool.handler(command="echo hello")
    assert result.success is True
    assert "hello" in result.output


def test_shell_blocked_command():
    tool = make_shell_tool(allowed_commands=["echo", "ls"])
    result = tool.handler(command="rm -rf /")
    assert result.success is False
    assert "nicht erlaubt" in result.output


def test_shell_pipe_blocked():
    tool = make_shell_tool()
    result = tool.handler(command="echo test | rm -rf /")
    assert result.success is False
    assert "Shell-Operator nicht erlaubt" in result.output


def test_shell_semicolon_blocked():
    tool = make_shell_tool()
    result = tool.handler(command="echo test; rm -rf /")
    assert result.success is False
    assert "Shell-Operator nicht erlaubt" in result.output


def test_shell_timeout():
    tool = make_shell_tool(allowed_commands=["sleep"], timeout=1)
    result = tool.handler(command="sleep 10")
    assert result.success is False
    assert "Timeout" in result.output


def test_shell_empty_command():
    tool = make_shell_tool()
    result = tool.handler(command="")
    assert result.success is False
    assert "Leerer Befehl" in result.output

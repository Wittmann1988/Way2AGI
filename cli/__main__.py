"""Way2AGI CLI Entry-Point."""
import click

@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """Way2AGI — Dein persoenlicher KI-Agent."""
    if ctx.invoked_subcommand is None:
        from cli.app import Way2AGIApp
        app = Way2AGIApp()
        app.run()

@main.command()
def chat():
    """Direkt in den Chat-Modus."""
    from cli.app import Way2AGIApp
    app = Way2AGIApp(start_screen="chat")
    app.run()

@main.command()
def doctor():
    """Systemdiagnose ausfuehren."""
    from cli.app import Way2AGIApp
    app = Way2AGIApp(start_screen="diagnostics")
    app.run()

if __name__ == "__main__":
    main()

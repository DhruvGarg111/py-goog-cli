"""Ask command - Natural language agent interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


@app.callback(invoke_without_command=True)
def ask_cmd(
    query: str | None = typer.Argument(None, help="Natural language query"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Deprecated compatibility flag; it cannot bypass local write confirmation",
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="LLM model (e.g., deepseek/deepseek-chat, gpt-4o)"
    ),
    allow_write: bool = typer.Option(
        False,
        "--allow-write",
        help="Expose write-capable tools (each write still requires local confirmation)",
    ),
    tools: str | None = typer.Option(
        None,
        "--tools",
        help="Comma-separated allowlist of agent tool names",
    ),
):
    """Ask pygog to do something using natural language.

    Examples:
        pygog ask "What are my unread emails?"
        pygog ask "Send an email to john@example.com saying the meeting is confirmed"
        pygog ask "Find the Q4 report and share it with finance@company.com"
    """
    if not query:
        console.print('[yellow]Usage: pygog ask "your question here"[/yellow]')
        console.print("\nExamples:")
        console.print('  pygog ask "What meetings do I have today?"')
        console.print('  pygog ask "Search for emails from my boss"')
        console.print('  pygog ask "List my Drive files"')
        raise typer.Exit(0)

    from pygog.cli import state

    try:
        from pygog.agent.core import run_agent

        if yes:
            err_console.print(
                "[yellow]Warning: --yes is deprecated and cannot bypass local write confirmation.[/yellow]"
            )

        result = run_agent(
            query=query,
            account=state.account,
            auto_confirm=False,
            model=model,
            allow_write=allow_write,
            allowed_tools=tools,
        )

        console.print()
        console.print(
            Panel(
                Markdown(result),
                title="[bold cyan]pygog[/bold cyan]",
                border_style="cyan",
            )
        )

    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        if state.verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)

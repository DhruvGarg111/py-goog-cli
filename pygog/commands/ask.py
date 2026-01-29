"""Ask command - Natural language agent interface."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


@app.callback(invoke_without_command=True)
def ask_cmd(
    query: Optional[str] = typer.Argument(None, help="Natural language query"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm destructive actions"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model (e.g., deepseek/deepseek-chat, gpt-4o)"),
):
    """Ask pygog to do something using natural language.
    
    Examples:
        pygog ask "What are my unread emails?"
        pygog ask "Send an email to john@example.com saying the meeting is confirmed"
        pygog ask "Find the Q4 report and share it with finance@company.com"
    """
    if not query:
        console.print("[yellow]Usage: pygog ask \"your question here\"[/yellow]")
        console.print("\nExamples:")
        console.print("  pygog ask \"What meetings do I have today?\"")
        console.print("  pygog ask \"Search for emails from my boss\"")
        console.print("  pygog ask \"List my Drive files\"")
        raise typer.Exit(0)
    
    from pygog.cli import state
    
    try:
        from pygog.agent.core import run_agent
        
        result = run_agent(
            query=query,
            account=state.account,
            auto_confirm=yes,
            model=model,
        )
        
        console.print()
        console.print(Panel(
            Markdown(result),
            title="[bold cyan]pygog[/bold cyan]",
            border_style="cyan",
        ))
        
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        if state.verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)

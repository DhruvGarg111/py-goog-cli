"""Tasks CLI commands."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pygog.services.tasks import TasksService
from pygog.output import print_json, print_plain

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def get_service() -> TasksService:
    """Get Tasks service for current account."""
    from pygog.cli import state
    return TasksService(account=state.account, client=state.client)


def should_json() -> bool:
    from pygog.cli import state
    return state.json_output


def should_plain() -> bool:
    from pygog.cli import state
    return state.plain_output



@app.command("lists")
def lists_cmd(
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
):
    """List all task lists."""
    service = get_service()
    tasklists = service.list_tasklists(max_results=max_results)

    if should_json():
        print_json({"tasklists": tasklists})
        return

    if not tasklists:
        console.print("[yellow]No task lists found.[/yellow]")
        return

    if should_plain():
        data = [{"id": t["id"], "title": t.get("title", "")} for t in tasklists]
        print_plain(data, columns=["id", "title"])
        return

    table = Table(title="Task Lists")
    table.add_column("Title", style="cyan")
    table.add_column("ID", style="dim")

    for tl in tasklists:
        table.add_row(tl.get("title", ""), tl["id"])

    console.print(table)


@app.command("create-list")
def create_list(
    title: str = typer.Argument(..., help="Task list title"),
):
    """Create a new task list."""
    service = get_service()
    result = service.create_tasklist(title)

    if should_json():
        print_json({"tasklist": result})
        return

    console.print(f"[green][OK][/green] Task list created: [cyan]{title}[/cyan]")
    console.print(f"  ID: {result['id']}")



@app.command("list")
def list_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
    show_completed: bool = typer.Option(True, "--show-completed/--hide-completed", help="Show completed tasks"),
):
    """List tasks in a task list."""
    service = get_service()
    tasks = service.list_tasks(
        tasklist_id,
        max_results=max_results,
        show_completed=show_completed,
    )

    if should_json():
        print_json({"tasks": tasks})
        return

    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    data = []
    for t in tasks:
        data.append({
            "id": t["id"],
            "title": t.get("title", ""),
            "status": t.get("status", ""),
            "due": TasksService.format_due(t.get("due")),
        })

    if should_plain():
        print_plain(data, columns=["id", "title", "status", "due"])
        return

    table = Table(title="Tasks")
    table.add_column("", width=1)
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Due")
    table.add_column("ID", style="dim")

    for d in data:
        icon = TasksService.get_status_icon(d["status"])
        style = "dim" if d["status"] == "completed" else ""
        table.add_row(icon, d["title"], d["due"], d["id"], style=style)

    console.print(table)


@app.command("get")
def get_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Get task details."""
    service = get_service()
    task = service.get_task(tasklist_id, task_id)

    if should_json():
        print_json({"task": task})
        return

    icon = TasksService.get_status_icon(task.get("status", ""))
    console.print(f"{icon} [bold]{task.get('title', '')}[/bold]")
    console.print(f"[bold]ID:[/bold] {task['id']}")
    console.print(f"[bold]Status:[/bold] {task.get('status', '')}")
    
    if task.get("due"):
        console.print(f"[bold]Due:[/bold] {TasksService.format_due(task['due'])}")
    
    if task.get("notes"):
        console.print(f"\n[bold]Notes:[/bold]")
        console.print(task["notes"])


@app.command("add")
def add_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    title: str = typer.Option(..., "--title", "-t", help="Task title"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Task notes"),
    due: Optional[str] = typer.Option(None, "--due", "-d", help="Due date (YYYY-MM-DD)"),
):
    """Add a new task."""
    service = get_service()
    task = service.create_task(
        tasklist_id,
        title=title,
        notes=notes,
        due=due,
    )

    if should_json():
        print_json({"task": task})
        return

    console.print(f"[green][OK][/green] Task added: [cyan]{title}[/cyan]")
    console.print(f"  ID: {task['id']}")


@app.command("update")
def update_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="New title"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="New notes"),
    due: Optional[str] = typer.Option(None, "--due", "-d", help="New due date"),
):
    """Update a task."""
    service = get_service()
    task = service.update_task(
        tasklist_id,
        task_id,
        title=title,
        notes=notes,
        due=due,
    )

    if should_json():
        print_json({"task": task})
        return

    console.print(f"[green][OK][/green] Task updated: {task_id}")


@app.command("done")
def done_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Mark a task as completed."""
    service = get_service()
    task = service.complete_task(tasklist_id, task_id)

    if should_json():
        print_json({"task": task})
        return

    console.print(f"[green][OK][/green] Task completed: {task.get('title', task_id)}")


@app.command("undo")
def undo_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Mark a task as not completed."""
    service = get_service()
    task = service.uncomplete_task(tasklist_id, task_id)

    if should_json():
        print_json({"task": task})
        return

    console.print(f"[green][OK][/green] Task marked incomplete: {task.get('title', task_id)}")


@app.command("delete")
def delete_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a task."""
    from pygog.cli import state

    if not force and not state.force:
        confirm = typer.confirm(f"Delete task {task_id}?")
        if not confirm:
            raise typer.Exit(0)

    service = get_service()
    service.delete_task(tasklist_id, task_id)

    if should_json():
        print_json({"deleted": True, "taskId": task_id})
        return

    console.print(f"[green][OK][/green] Task deleted: {task_id}")


@app.command("clear")
def clear_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear all completed tasks from a list."""
    from pygog.cli import state

    if not force and not state.force:
        confirm = typer.confirm("Clear all completed tasks?")
        if not confirm:
            raise typer.Exit(0)

    service = get_service()
    service.clear_completed(tasklist_id)

    if should_json():
        print_json({"cleared": True, "tasklistId": tasklist_id})
        return

    console.print(f"[green][OK][/green] Completed tasks cleared")

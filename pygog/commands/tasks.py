"""Tasks CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from pygog.interaction import confirm_destructive, dry_run_output, execute_mutation
from pygog.output import print_json, print_plain
from pygog.services.tasks import TasksService

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


def _account_preview() -> str:
    from pygog.cli import state

    return state.account or "(current account)"


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

    if should_plain():
        data = [{"id": t["id"], "title": t.get("title", "")} for t in tasklists]
        print_plain(data, columns=["id", "title"], header_on_empty=True)
        return

    if not tasklists:
        console.print("[yellow]No task lists found.[/yellow]")
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
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Create a new task list."""
    if dry_run:
        dry_run_output(
            "create task list",
            {"title": title},
            plain_columns=["dryRun", "action", "title"],
            console=console,
        )
        return

    confirm_destructive(
        "create task list",
        f"title={title!r}, account={_account_preview()}",
        local_force=force,
    )
    result = execute_mutation(
        lambda: get_service().create_tasklist(title),
        action="create task list",
    )

    if should_json():
        print_json({"tasklist": result})
        return

    if should_plain():
        print_plain(
            [{"id": result["id"], "title": result.get("title", title)}], columns=["id", "title"]
        )
        return

    console.print(f"[green][OK][/green] Task list created: [cyan]{title}[/cyan]")
    console.print(f"  ID: {result['id']}")


@app.command("list")
def list_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
    show_completed: bool = typer.Option(
        True, "--show-completed/--hide-completed", help="Show completed tasks"
    ),
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

    data = []
    for t in tasks:
        data.append(
            {
                "id": t["id"],
                "title": t.get("title", ""),
                "status": t.get("status", ""),
                "due": TasksService.format_due(t.get("due")),
            }
        )

    if should_plain():
        print_plain(data, columns=["id", "title", "status", "due"], header_on_empty=True)
        return

    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
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
        console.print("\n[bold]Notes:[/bold]")
        console.print(task["notes"])


@app.command("add")
def add_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    title: str = typer.Option(..., "--title", "-t", help="Task title"),
    notes: str | None = typer.Option(None, "--notes", "-n", help="Task notes"),
    due: str | None = typer.Option(None, "--due", "-d", help="Due date (YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Add a new task."""
    details = {"tasklistId": tasklist_id, "title": title, "due": due or ""}
    if dry_run:
        dry_run_output(
            "add task",
            details,
            plain_columns=["dryRun", "action", "tasklistId", "title", "due"],
            console=console,
        )
        return

    confirm_destructive(
        "add task",
        f"tasklist={tasklist_id}, title={title!r}, due={due or '(none)'}, account={_account_preview()}",
        local_force=force,
    )
    task = execute_mutation(
        lambda: get_service().create_task(
            tasklist_id,
            title=title,
            notes=notes,
            due=due,
        ),
        action="add task",
    )

    if should_json():
        print_json({"task": task})
        return

    if should_plain():
        print_plain(
            [{"taskId": task.get("id", ""), "title": task.get("title", title), "due": due or ""}],
            columns=["taskId", "title", "due"],
        )
        return

    console.print(f"[green][OK][/green] Task added: [cyan]{title}[/cyan]")
    console.print(f"  ID: {task['id']}")


@app.command("update")
def update_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    title: str | None = typer.Option(None, "--title", "-t", help="New title"),
    notes: str | None = typer.Option(None, "--notes", "-n", help="New notes"),
    due: str | None = typer.Option(None, "--due", "-d", help="New due date"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Update a task."""
    changes = {key: value for key, value in (("title", title), ("due", due)) if value is not None}
    details = {"tasklistId": tasklist_id, "taskId": task_id, **changes}
    if dry_run:
        dry_run_output(
            "update task",
            details,
            plain_columns=["dryRun", "action", "tasklistId", "taskId", *changes.keys()],
            console=console,
        )
        return

    confirm_destructive(
        "update task",
        f"tasklist={tasklist_id}, task={task_id}, changes={changes or '(none)'}, "
        f"account={_account_preview()}",
        local_force=force,
    )
    task = execute_mutation(
        lambda: get_service().update_task(
            tasklist_id,
            task_id,
            title=title,
            notes=notes,
            due=due,
        ),
        action="update task",
    )

    if should_json():
        print_json({"task": task})
        return

    if should_plain():
        print_plain(
            [{"taskId": task.get("id", task_id), **changes}],
            columns=["taskId", *changes.keys()],
        )
        return

    console.print(f"[green][OK][/green] Task updated: {task_id}")


@app.command("done")
def done_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Mark a task as completed."""
    if dry_run:
        dry_run_output(
            "complete task",
            {"tasklistId": tasklist_id, "taskId": task_id},
            plain_columns=["dryRun", "action", "tasklistId", "taskId"],
            console=console,
        )
        return

    confirm_destructive(
        "complete task",
        f"tasklist={tasklist_id}, task={task_id}, account={_account_preview()}",
        local_force=force,
    )
    task = execute_mutation(
        lambda: get_service().complete_task(tasklist_id, task_id),
        action="complete task",
    )

    if should_json():
        print_json({"task": task})
        return

    if should_plain():
        print_plain([{"taskId": task_id, "status": "completed"}], columns=["taskId", "status"])
        return

    console.print(f"[green][OK][/green] Task completed: {task.get('title', task_id)}")


@app.command("undo")
def undo_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Mark a task as not completed."""
    if dry_run:
        dry_run_output(
            "reopen task",
            {"tasklistId": tasklist_id, "taskId": task_id},
            plain_columns=["dryRun", "action", "tasklistId", "taskId"],
            console=console,
        )
        return

    confirm_destructive(
        "reopen task",
        f"tasklist={tasklist_id}, task={task_id}, account={_account_preview()}",
        local_force=force,
    )
    task = execute_mutation(
        lambda: get_service().uncomplete_task(tasklist_id, task_id),
        action="reopen task",
    )

    if should_json():
        print_json({"task": task})
        return

    if should_plain():
        print_plain([{"taskId": task_id, "status": "needsAction"}], columns=["taskId", "status"])
        return

    console.print(f"[green][OK][/green] Task marked incomplete: {task.get('title', task_id)}")


@app.command("delete")
def delete_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Delete a task."""
    if dry_run:
        dry_run_output(
            "delete task",
            {"tasklistId": tasklist_id, "taskId": task_id},
            plain_columns=["dryRun", "action", "tasklistId", "taskId"],
            console=console,
        )
        return

    confirm_destructive(
        "delete task",
        f"tasklist={tasklist_id}, task={task_id}, account={_account_preview()}",
        local_force=force,
    )

    execute_mutation(
        lambda: get_service().delete_task(tasklist_id, task_id),
        action="delete task",
    )

    if should_json():
        print_json({"deleted": True, "taskId": task_id})
        return

    if should_plain():
        print_plain([{"deleted": True, "taskId": task_id}], columns=["deleted", "taskId"])
        return

    console.print(f"[green][OK][/green] Task deleted: {task_id}")


@app.command("clear")
def clear_cmd(
    tasklist_id: str = typer.Argument(..., help="Task list ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Clear all completed tasks from a list."""
    if dry_run:
        dry_run_output(
            "clear completed tasks",
            {"tasklistId": tasklist_id},
            plain_columns=["dryRun", "action", "tasklistId"],
            console=console,
        )
        return

    confirm_destructive(
        "clear completed tasks",
        f"tasklist={tasklist_id}, account={_account_preview()}",
        local_force=force,
    )

    execute_mutation(
        lambda: get_service().clear_completed(tasklist_id),
        action="clear completed tasks",
    )

    if should_json():
        print_json({"cleared": True, "tasklistId": tasklist_id})
        return

    if should_plain():
        print_plain(
            [{"cleared": True, "tasklistId": tasklist_id}], columns=["cleared", "tasklistId"]
        )
        return

    console.print("[green][OK][/green] Completed tasks cleared")

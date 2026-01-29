"""Tasks API service wrapper."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pygog.services.base import BaseService


class TasksService(BaseService):
    """Tasks API service wrapper."""

    SERVICE_NAME = "tasks"
    SERVICE_VERSION = "v1"

    def _tasklists(self):
        """Get tasklists API."""
        return self._get_service().tasklists()

    def _tasks(self):
        """Get tasks API."""
        return self._get_service().tasks()

    # =========================================================================
    # Task Lists
    # =========================================================================

    def list_tasklists(self, max_results: int = 100) -> list[dict[str, Any]]:
        """List all task lists.
        
        Returns:
            List of task list dicts
        """
        result = self._tasklists().list(maxResults=max_results).execute()
        return result.get("items", [])

    def get_tasklist(self, tasklist_id: str) -> dict[str, Any]:
        """Get a task list by ID.
        
        Args:
            tasklist_id: Task list ID
            
        Returns:
            Task list dict
        """
        return self._tasklists().get(tasklist=tasklist_id).execute()

    def create_tasklist(self, title: str) -> dict[str, Any]:
        """Create a new task list.
        
        Args:
            title: Task list title
            
        Returns:
            Created task list dict
        """
        return self._tasklists().insert(body={"title": title}).execute()

    def update_tasklist(self, tasklist_id: str, title: str) -> dict[str, Any]:
        """Update a task list.
        
        Args:
            tasklist_id: Task list ID
            title: New title
            
        Returns:
            Updated task list dict
        """
        return self._tasklists().update(
            tasklist=tasklist_id,
            body={"title": title},
        ).execute()

    def delete_tasklist(self, tasklist_id: str) -> None:
        """Delete a task list.
        
        Args:
            tasklist_id: Task list ID
        """
        self._tasklists().delete(tasklist=tasklist_id).execute()

    # =========================================================================
    # Tasks
    # =========================================================================

    def list_tasks(
        self,
        tasklist_id: str,
        max_results: int = 100,
        show_completed: bool = True,
        show_hidden: bool = False,
    ) -> list[dict[str, Any]]:
        """List tasks in a task list.
        
        Args:
            tasklist_id: Task list ID
            max_results: Maximum tasks to return
            show_completed: Include completed tasks
            show_hidden: Include hidden tasks
            
        Returns:
            List of task dicts
        """
        result = self._tasks().list(
            tasklist=tasklist_id,
            maxResults=max_results,
            showCompleted=show_completed,
            showHidden=show_hidden,
        ).execute()
        return result.get("items", [])

    def get_task(self, tasklist_id: str, task_id: str) -> dict[str, Any]:
        """Get a task by ID.
        
        Args:
            tasklist_id: Task list ID
            task_id: Task ID
            
        Returns:
            Task dict
        """
        return self._tasks().get(tasklist=tasklist_id, task=task_id).execute()

    def create_task(
        self,
        tasklist_id: str,
        title: str,
        notes: str | None = None,
        due: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Create a new task.
        
        Args:
            tasklist_id: Task list ID
            title: Task title
            notes: Optional notes/description
            due: Optional due date (RFC 3339 or datetime)
            
        Returns:
            Created task dict
        """
        task = {"title": title}
        
        if notes:
            task["notes"] = notes
        
        if due:
            if isinstance(due, datetime):
                # Google Tasks expects date-only in RFC 3339 format
                due = due.strftime("%Y-%m-%dT00:00:00.000Z")
            elif not due.endswith("Z") and "T" not in due:
                # Convert date string to RFC 3339
                due = f"{due}T00:00:00.000Z"
            task["due"] = due

        return self._tasks().insert(tasklist=tasklist_id, body=task).execute()

    def update_task(
        self,
        tasklist_id: str,
        task_id: str,
        title: str | None = None,
        notes: str | None = None,
        due: str | datetime | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Update a task.
        
        Args:
            tasklist_id: Task list ID
            task_id: Task ID
            title: New title
            notes: New notes
            due: New due date
            status: 'needsAction' or 'completed'
            
        Returns:
            Updated task dict
        """
        # Get existing task
        task = self.get_task(tasklist_id, task_id)

        if title is not None:
            task["title"] = title
        if notes is not None:
            task["notes"] = notes
        if due is not None:
            if isinstance(due, datetime):
                due = due.strftime("%Y-%m-%dT00:00:00.000Z")
            elif not due.endswith("Z") and "T" not in due:
                due = f"{due}T00:00:00.000Z"
            task["due"] = due
        if status is not None:
            task["status"] = status

        return self._tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=task,
        ).execute()

    def complete_task(self, tasklist_id: str, task_id: str) -> dict[str, Any]:
        """Mark a task as completed.
        
        Args:
            tasklist_id: Task list ID
            task_id: Task ID
            
        Returns:
            Updated task dict
        """
        return self.update_task(tasklist_id, task_id, status="completed")

    def uncomplete_task(self, tasklist_id: str, task_id: str) -> dict[str, Any]:
        """Mark a task as not completed.
        
        Args:
            tasklist_id: Task list ID
            task_id: Task ID
            
        Returns:
            Updated task dict
        """
        return self.update_task(tasklist_id, task_id, status="needsAction")

    def delete_task(self, tasklist_id: str, task_id: str) -> None:
        """Delete a task.
        
        Args:
            tasklist_id: Task list ID
            task_id: Task ID
        """
        self._tasks().delete(tasklist=tasklist_id, task=task_id).execute()

    def clear_completed(self, tasklist_id: str) -> None:
        """Clear all completed tasks from a list.
        
        Args:
            tasklist_id: Task list ID
        """
        self._tasks().clear(tasklist=tasklist_id).execute()

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def format_due(due: str | None) -> str:
        """Format due date for display.
        
        Args:
            due: RFC 3339 due date string
            
        Returns:
            Formatted date string
        """
        if not due:
            return ""
        try:
            dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return due

    @staticmethod
    def get_status_icon(status: str) -> str:
        """Get status icon for display.
        
        Args:
            status: Task status
            
        Returns:
            Icon character
        """
        return "[OK]" if status == "completed" else "[ ]"

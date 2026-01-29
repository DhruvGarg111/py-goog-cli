"""Google API service wrappers."""

from __future__ import annotations

from .base import BaseService
from .gmail import GmailService
from .calendar import CalendarService
from .drive import DriveService
from .tasks import TasksService

__all__ = [
    "BaseService",
    "GmailService",
    "CalendarService",
    "DriveService",
    "TasksService",
]

"""Tool wrappers for the agent to call pygog services."""

from __future__ import annotations

from typing import Optional

from pygog.agent.registry import register_tool


@register_tool()
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for real-time information like prices, news, weather, etc.
    
    Args:
        query: Search query (e.g., 'gold price Delhi 24kt', 'weather Mumbai', 'latest news India')
        max_results: Maximum number of results to return
        
    Returns:
        List of search results with title, body, and url
    """
    from ddgs import DDGS
    
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("href", ""),
                })
    except Exception as e:
        return [{"error": str(e)}]
    
    return results


@register_tool()
def web_news(query: str, max_results: int = 5) -> list[dict]:
    """Search for latest news articles.
    
    Args:
        query: News topic to search for (e.g., 'stock market', 'tech news')
        max_results: Maximum number of articles to return
        
    Returns:
        List of news articles with title, body, date, and url
    """
    from ddgs import DDGS
    
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "date": r.get("date", ""),
                    "source": r.get("source", ""),
                    "url": r.get("url", ""),
                })
    except Exception as e:
        return [{"error": str(e)}]
    
    return results


@register_tool()
def gmail_search(query: str, max_results: int = 10, account: Optional[str] = None) -> list[dict]:
    """Search for emails in Gmail.
    
    Args:
        query: Gmail search query (e.g., 'from:boss newer_than:7d', 'is:unread', 'subject:report')
        max_results: Maximum number of threads to return
        account: Google account email
        
    Returns:
        List of matching email threads with id, subject, from, and date
    """
    from pygog.services.gmail import GmailService
    
    service = GmailService(account=account)
    response = service.search_threads(query=query, max_results=max_results)
    
    threads = response.get("threads", [])
    results = []
    
    for thread_info in threads:
        thread_id = thread_info.get("id")
        if not thread_id:
            continue
        
        try:
            thread = service.get_thread(thread_id, format="metadata")
            messages = thread.get("messages", [])
            if not messages:
                continue
                
            msg = messages[0]
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            
            results.append({
                "thread_id": thread_id,
                "subject": headers.get("subject", "(no subject)"),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
                "snippet": thread.get("snippet", "")[:100],
            })
        except Exception:
            continue
    
    return results


@register_tool()
def gmail_get_message(thread_id: str, account: Optional[str] = None) -> dict:
    """Get details of a specific email thread.
    
    Args:
        thread_id: The Gmail thread ID
        account: Google account email
        
    Returns:
        Thread details including messages, subject, and body
    """
    from pygog.services.gmail import GmailService
    
    service = GmailService(account=account)
    thread = service.get_thread(thread_id)
    
    messages = []
    for msg in thread.get("messages", []):
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        body = ""
        payload = msg.get("payload", {})
        if payload.get("body", {}).get("data"):
            import base64
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        
        messages.append({
            "id": msg.get("id"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "body_preview": body[:500] if body else msg.get("snippet", ""),
        })
    
    return {"thread_id": thread_id, "messages": messages}


@register_tool(destructive=True)
def gmail_send(to: str, subject: str, body: str, cc: Optional[str] = None, account: Optional[str] = None) -> dict:
    """Send an email via Gmail.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain text body of the email
        cc: Optional CC recipient
        account: Google account email
        
    Returns:
        Sent message details including ID
    """
    from pygog.services.gmail import GmailService
    
    service = GmailService(account=account)
    result = service.send_message(to=to, subject=subject, body=body, cc=cc)
    
    return {"message_id": result.get("id"), "status": "sent", "to": to, "subject": subject}


@register_tool()
def gmail_labels(account: Optional[str] = None) -> list[dict]:
    """List all Gmail labels.
    
    Args:
        account: Google account email
        
    Returns:
        List of labels with id and name
    """
    from pygog.services.gmail import GmailService
    
    service = GmailService(account=account)
    labels = service.list_labels()
    
    return [{"id": l["id"], "name": l.get("name", l["id"]), "type": l.get("type", "user")} for l in labels]


@register_tool()
def drive_list(folder_id: Optional[str] = None, max_results: int = 20, account: Optional[str] = None) -> list[dict]:
    """List files in Google Drive.
    
    Args:
        folder_id: Optional folder ID to list (default: root)
        max_results: Maximum number of files to return
        account: Google account email
        
    Returns:
        List of files with id, name, type, and modified time
    """
    from pygog.services.drive import DriveService
    
    service = DriveService(account=account)
    files = service.list_files(folder_id=folder_id, max_results=max_results)
    
    return [{
        "id": f["id"],
        "name": f.get("name", ""),
        "type": "folder" if f.get("mimeType") == "application/vnd.google-apps.folder" else "file",
        "mime_type": f.get("mimeType", ""),
        "modified": f.get("modifiedTime", ""),
    } for f in files]


@register_tool()
def drive_search(query: str, max_results: int = 20, account: Optional[str] = None) -> list[dict]:
    """Search for files in Google Drive.
    
    Args:
        query: Search query (e.g., 'name contains "report"', 'resume.pdf', 'type:pdf')
        max_results: Maximum number of files to return
        account: Google account email
        
    Returns:
        List of matching files with id, name, and type
    """
    from pygog.services.drive import DriveService
    
    service = DriveService(account=account)
    
    if ":" not in query and "contains" not in query:
        query = f"name contains '{query}'"
    
    files = service.search_files(query=query, max_results=max_results)
    
    return [{
        "id": f["id"],
        "name": f.get("name", ""),
        "type": "folder" if f.get("mimeType") == "application/vnd.google-apps.folder" else "file",
        "mime_type": f.get("mimeType", ""),
        "web_link": f.get("webViewLink", ""),
    } for f in files]


@register_tool()
def drive_get_file(file_id: str, account: Optional[str] = None) -> dict:
    """Get metadata for a specific file in Drive.
    
    Args:
        file_id: The Drive file ID
        account: Google account email
        
    Returns:
        File metadata including name, size, and sharing info
    """
    from pygog.services.drive import DriveService
    
    service = DriveService(account=account)
    file = service.get_file(file_id)
    
    return {
        "id": file["id"],
        "name": file.get("name", ""),
        "mime_type": file.get("mimeType", ""),
        "size": file.get("size", ""),
        "web_link": file.get("webViewLink", ""),
        "created": file.get("createdTime", ""),
        "modified": file.get("modifiedTime", ""),
    }


@register_tool(destructive=True)
def drive_share(file_id: str, email: str, role: str = "reader", account: Optional[str] = None) -> dict:
    """Share a Drive file with someone.
    
    Args:
        file_id: The Drive file ID
        email: Email address to share with
        role: Permission role (reader, writer, commenter)
        account: Google account email
        
    Returns:
        Share confirmation
    """
    from pygog.services.drive import DriveService
    
    service = DriveService(account=account)
    service.share_file(file_id=file_id, email=email, role=role)
    
    return {"status": "shared", "file_id": file_id, "shared_with": email, "role": role}


@register_tool()
def calendar_events(days: int = 7, calendar_id: str = "primary", account: Optional[str] = None) -> list[dict]:
    """List upcoming calendar events.
    
    Args:
        days: Number of days to look ahead (default: 7)
        calendar_id: Calendar ID (default: primary)
        account: Google account email
        
    Returns:
        List of upcoming events with summary, time, and attendees
    """
    from datetime import datetime, timedelta
    from pygog.services.calendar import CalendarService
    
    service = CalendarService(account=account)
    
    now = datetime.now()
    time_min = now
    time_max = now + timedelta(days=days)
    
    response = service.list_events(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
    )
    events = response.get("items", [])
    
    result = []
    for event in events:
        start = event.get("start", {})
        start_time = start.get("dateTime") or start.get("date", "")
        
        result.append({
            "id": event["id"],
            "summary": event.get("summary", "(No title)"),
            "start": start_time,
            "location": event.get("location", ""),
            "status": event.get("status", ""),
        })
    
    return result


@register_tool()
def calendar_search(query: str, days: int = 30, account: Optional[str] = None) -> list[dict]:
    """Search for calendar events.
    
    Args:
        query: Search query (matches event title/description)
        days: Number of days to search ahead
        account: Google account email
        
    Returns:
        List of matching events
    """
    from datetime import datetime, timedelta
    from pygog.services.calendar import CalendarService
    
    service = CalendarService(account=account)
    
    now = datetime.now()
    time_min = now - timedelta(days=30)  # Also search past 30 days
    time_max = now + timedelta(days=days)
    
    response = service.list_events(
        calendar_id="primary",
        time_min=time_min,
        time_max=time_max,
        q=query,
    )
    events = response.get("items", [])
    
    result = []
    for event in events:
        start = event.get("start", {})
        start_time = start.get("dateTime") or start.get("date", "")
        
        result.append({
            "id": event["id"],
            "summary": event.get("summary", "(No title)"),
            "start": start_time,
            "location": event.get("location", ""),
        })
    
    return result


@register_tool(destructive=True)
def calendar_create(summary: str, start_time: str, end_time: str, description: Optional[str] = None, 
                   location: Optional[str] = None, attendees: Optional[str] = None,
                   account: Optional[str] = None) -> dict:
    """Create a new calendar event.
    
    Args:
        summary: Event title
        start_time: Start time in ISO format (e.g., 2026-02-01T10:00:00)
        end_time: End time in ISO format
        description: Optional event description
        location: Optional event location
        attendees: Optional comma-separated list of attendee emails
        account: Google account email
        
    Returns:
        Created event details
    """
    from pygog.services.calendar import CalendarService
    
    service = CalendarService(account=account)
    
    attendee_list = None
    if attendees:
        attendee_list = [e.strip() for e in attendees.split(",")]
    
    event = service.create_event(
        calendar_id="primary",
        summary=summary,
        start=start_time,
        end=end_time,
        description=description,
        location=location,
        attendees=attendee_list,
    )
    
    return {"id": event["id"], "summary": summary, "start": start_time, "status": "created"}


@register_tool()
def tasks_lists(account: Optional[str] = None) -> list[dict]:
    """List all task lists.
    
    Args:
        account: Google account email
        
    Returns:
        List of task lists with id and title
    """
    from pygog.services.tasks import TasksService
    
    service = TasksService(account=account)
    tasklists = service.list_tasklists()
    
    return [{"id": tl["id"], "title": tl.get("title", "")} for tl in tasklists]


@register_tool()
def tasks_list(tasklist_id: str, show_completed: bool = False, account: Optional[str] = None) -> list[dict]:
    """List tasks in a task list.
    
    Args:
        tasklist_id: The task list ID
        show_completed: Whether to include completed tasks
        account: Google account email
        
    Returns:
        List of tasks with id, title, status, and due date
    """
    from pygog.services.tasks import TasksService
    
    service = TasksService(account=account)
    tasks = service.list_tasks(tasklist_id, show_completed=show_completed)
    
    return [{
        "id": t["id"],
        "title": t.get("title", ""),
        "status": t.get("status", ""),
        "due": t.get("due", ""),
        "notes": t.get("notes", "")[:100] if t.get("notes") else "",
    } for t in tasks]


@register_tool(destructive=True)
def tasks_add(tasklist_id: str, title: str, notes: Optional[str] = None, due: Optional[str] = None,
              account: Optional[str] = None) -> dict:
    """Add a new task to a task list.
    
    Args:
        tasklist_id: The task list ID
        title: Task title
        notes: Optional task notes
        due: Optional due date (YYYY-MM-DD)
        account: Google account email
        
    Returns:
        Created task details
    """
    from pygog.services.tasks import TasksService
    
    service = TasksService(account=account)
    task = service.create_task(tasklist_id, title=title, notes=notes, due=due)
    
    return {"id": task["id"], "title": title, "status": "created"}


@register_tool(destructive=True)
def tasks_complete(tasklist_id: str, task_id: str, account: Optional[str] = None) -> dict:
    """Mark a task as completed.
    
    Args:
        tasklist_id: The task list ID
        task_id: The task ID
        account: Google account email
        
    Returns:
        Updated task status
    """
    from pygog.services.tasks import TasksService
    
    service = TasksService(account=account)
    task = service.complete_task(tasklist_id, task_id)
    
    return {"id": task_id, "title": task.get("title", ""), "status": "completed"}

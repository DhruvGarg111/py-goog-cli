"""Core agent loop with liteLLM for provider-agnostic LLM support."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from pygog.agent.registry import TOOLS_REGISTRY, get_all_tool_schemas, is_destructive

console = Console()
err_console = Console(stderr=True)

DEFAULT_MODEL = "deepseek/deepseek-chat"

SYSTEM_PROMPT = """You are pygog, an intelligent assistant for Google Workspace.
Today is {date}.

You help users interact with their Gmail, Google Drive, Calendar, and Tasks using natural language.

Guidelines:
- If a request is ambiguous, ask for clarification before proceeding.
- For multi-step tasks, execute them in sequence.
- Always confirm destructive actions (send, delete, upload) with the user.
- Provide concise, helpful responses.
- When listing items, summarize the key information.

Available capabilities:
- Gmail: Search emails, send emails, manage labels
- Drive: List and search files, upload/download, share
- Calendar: View and manage events, check availability
- Tasks: Manage task lists and tasks
"""


def get_model_name() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter/deepseek/deepseek-chat"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek/deepseek-chat"
    if os.environ.get("OPENAI_API_KEY"):
        return "gpt-4o-mini"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini/gemini-2.0-flash"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude-3-haiku-20240307"
        
    raise ValueError(
        "No LLM API key found. Set one of:\n"
        "  - OPENROUTER_API_KEY\n"
        "  - DEEPSEEK_API_KEY\n"
        "  - OPENAI_API_KEY\n"
        "  - GEMINI_API_KEY\n"
        "  - ANTHROPIC_API_KEY"
    )


def build_tools_for_litellm() -> list[dict[str, Any]]:
    tools = []
    for schema in get_all_tool_schemas():
        tools.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"],
            }
        })
    return tools


def execute_tool(func_name: str, args: dict[str, Any], account: str | None = None) -> Any:
    tool = TOOLS_REGISTRY.get(func_name)
    if not tool:
        return {"error": f"Unknown tool: {func_name}"}
    
    func = tool["function"]
    
    import inspect
    sig = inspect.signature(func)
    if "account" in sig.parameters and account:
        args["account"] = account
    
    try:
        return func(**args)
    except Exception as e:
        return {"error": str(e)}


def format_tool_call_summary(func_name: str, args: dict[str, Any]) -> str:
    if func_name == "gmail_send":
        return f"Send email to '{args.get('to', '?')}' with subject '{args.get('subject', '?')}'"
    if func_name == "drive_upload":
        return f"Upload file '{args.get('file_path', '?')}' to Drive"
    if func_name == "drive_delete":
        return f"Delete file '{args.get('file_id', '?')}' from Drive"
    if func_name == "drive_share":
        return f"Share file with '{args.get('email', '?')}'"
    if func_name == "calendar_create":
        return f"Create event '{args.get('summary', '?')}'"
    if func_name == "calendar_delete":
        return f"Delete event '{args.get('event_id', '?')}'"
    if func_name == "tasks_add":
        return f"Add task '{args.get('title', '?')}'"
    if func_name == "tasks_complete":
        return f"Complete task '{args.get('task_id', '?')}'"
    
    args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
    return f"Call {func_name}({args_str})"


def run_agent(
    query: str, 
    account: str | None = None, 
    auto_confirm: bool = False,
    model: str | None = None,
) -> str:
    import litellm
    from pygog.agent import tools  # noqa: F401
    
    model_name = model or get_model_name()
    console.print(f"[dim]Using model: {model_name}[/dim]")
    
    tool_defs = build_tools_for_litellm()
    if not tool_defs:
        return "No tools available. Please ensure tools are registered."
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(date=datetime.now().strftime("%A, %B %d, %Y"))},
        {"role": "user", "content": query},
    ]
    
    console.print(f"\n[dim]Thinking...[/dim]")
    
    max_iterations = 10
    
    for _ in range(max_iterations):
        try:
            response = litellm.completion(
                model=model_name,
                messages=messages,
                tools=tool_defs,
                tool_choice="auto",
            )
        except Exception as e:
            return f"Error calling LLM: {e}"
        
        response_message = response.choices[0].message
        
        if not response_message.tool_calls:
            return response_message.content or "I was unable to complete your request."
            
        messages.append(response_message.model_dump())
        
        for tool_call in response_message.tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                func_args = {}
            
            console.print(f"\n[cyan]> {format_tool_call_summary(func_name, func_args)}[/cyan]")
            
            if is_destructive(func_name) and not auto_confirm:
                summary = format_tool_call_summary(func_name, func_args)
                console.print(Panel(
                    f"[yellow]This action will modify data:[/yellow]\n{summary}",
                    title="Confirmation Required",
                    border_style="yellow",
                ))
                
                if not Confirm.ask("Proceed?", default=False):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": "User declined to execute this action."}),
                    })
                    continue
            
            result = execute_tool(func_name, func_args, account)
            
            if isinstance(result, dict) and "error" in result:
                console.print(f"[red]Error: {result['error']}[/red]")
            elif isinstance(result, list):
                console.print(f"[green]Got {len(result)} results[/green]")
            else:
                console.print(f"[green]Done[/green]")
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })
    
    return "Maximum iterations reached. Please try a simpler request."

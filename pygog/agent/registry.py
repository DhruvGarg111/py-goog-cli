"""Tool registry for LLM function calling."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

TOOLS_REGISTRY: dict[str, dict[str, Any]] = {}

DESTRUCTIVE_KEYWORDS = [
    "send",
    "delete",
    "upload",
    "update",
    "create",
    "remove",
    "move",
    "share",
    "trash",
]


def get_type_schema(python_type: type) -> dict[str, Any]:
    """Convert Python type to JSON schema type."""
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    origin = getattr(python_type, "__origin__", None)
    if origin is list:
        args = getattr(python_type, "__args__", (str,))
        return {"type": "array", "items": get_type_schema(args[0]) if args else {"type": "string"}}

    return type_map.get(python_type, {"type": "string"})


def generate_schema_from_function(func: Callable) -> dict[str, Any]:
    """Generate Gemini function declaration schema from a Python function."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    docstring = inspect.getdoc(func) or ""

    param_docs = {}
    if "Args:" in docstring:
        args_section = docstring.split("Args:")[1]
        if "Returns:" in args_section:
            args_section = args_section.split("Returns:")[0]
        for line in args_section.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                param_name, param_desc = line.split(":", 1)
                param_docs[param_name.strip()] = param_desc.strip()

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "account", "client"):
            continue

        param_type = hints.get(param_name, str)

        origin = get_origin(param_type)
        if origin in (Union, UnionType) and type(None) in get_args(param_type):
            args = tuple(arg for arg in get_args(param_type) if arg is not type(None))
            param_type = args[0] if args else str

        prop_schema = get_type_schema(param_type)
        prop_schema["description"] = param_docs.get(param_name, f"The {param_name} parameter")
        properties[param_name] = prop_schema

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    description = docstring.split("\n")[0] if docstring else func.__name__

    return {
        "name": func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def register_tool(*, destructive: bool | None = None):
    """Decorator to register a function as an LLM-callable tool.

    Args:
        destructive: If True, requires user confirmation before execution.
                    If None, auto-detects based on function name.
    """

    def decorator(func: Callable) -> Callable:
        func_name = func.__name__

        is_destructive = destructive
        if is_destructive is None:
            is_destructive = any(kw in func_name.lower() for kw in DESTRUCTIVE_KEYWORDS)

        schema = generate_schema_from_function(func)

        TOOLS_REGISTRY[func_name] = {
            "function": func,
            "schema": schema,
            "destructive": is_destructive,
        }

        return func

    return decorator


def get_all_tool_schemas() -> list[dict[str, Any]]:
    """Get all registered tool schemas for Gemini."""
    return [tool["schema"] for tool in TOOLS_REGISTRY.values()]


def get_tool(name: str) -> dict[str, Any] | None:
    """Get a registered tool by name."""
    return TOOLS_REGISTRY.get(name)


def is_destructive(name: str) -> bool:
    """Check if a tool is destructive."""
    tool = TOOLS_REGISTRY.get(name)
    return tool["destructive"] if tool else False

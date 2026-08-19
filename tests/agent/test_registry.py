import pytest

from pygog.agent.registry import (
    TOOLS_REGISTRY,
    generate_schema_from_function,
    get_type_schema,
    is_destructive,
    register_tool,
)


@pytest.fixture(autouse=True)
def restore_tools_registry():
    snapshot = TOOLS_REGISTRY.copy()
    yield
    TOOLS_REGISTRY.clear()
    TOOLS_REGISTRY.update(snapshot)


def test_optional_parameter_without_default_is_required():
    def lookup(folder_id: str | None):
        """Look up a folder.

        Args:
            folder_id: Folder identifier
        """

    schema = generate_schema_from_function(lookup)

    assert schema["parameters"]["properties"]["folder_id"] == {
        "type": "string",
        "description": "Folder identifier",
    }
    assert schema["parameters"]["required"] == ["folder_id"]


def test_optional_parameter_with_default_is_not_required():
    def lookup(folder_id: str | None = None):
        """Look up a folder."""

    schema = generate_schema_from_function(lookup)

    assert schema["parameters"]["required"] == []


def test_pep604_optional_parameter_without_default_is_required():
    def lookup(folder_id: str | None):
        """Look up a folder."""

    schema = generate_schema_from_function(lookup)

    assert schema["parameters"]["required"] == ["folder_id"]


def test_list_type_includes_item_schema():
    assert get_type_schema(list[int]) == {
        "type": "array",
        "items": {"type": "integer"},
    }


def test_primitive_defaults_are_schema_typed_and_not_required():
    def configure(
        name: str = "default",
        retries: int = 2,
        ratio: float = 0.5,
        enabled: bool = True,
    ):
        """Configure a tool."""

    parameters = generate_schema_from_function(configure)["parameters"]

    assert parameters["properties"] == {
        "name": {"type": "string", "description": "The name parameter"},
        "retries": {"type": "integer", "description": "The retries parameter"},
        "ratio": {"type": "number", "description": "The ratio parameter"},
        "enabled": {"type": "boolean", "description": "The enabled parameter"},
    }
    assert parameters["required"] == []


def test_required_fields_are_included_in_required_list():
    def create_event(summary: str, attendees: list[str], calendar_id: str = "primary"):
        """Create an event."""

    parameters = generate_schema_from_function(create_event)["parameters"]

    assert parameters["required"] == ["summary", "attendees"]


def test_destructive_metadata_supports_explicit_and_auto_detection():
    @register_tool(destructive=True)
    def archive_record(record_id: str):
        """Archive a record."""

    @register_tool()
    def upload_record(record_id: str):
        """Upload a record."""

    @register_tool(destructive=False)
    def delete_record(record_id: str):
        """Delete a record without changing data."""

    assert TOOLS_REGISTRY["archive_record"]["destructive"] is True
    assert is_destructive("archive_record") is True
    assert TOOLS_REGISTRY["upload_record"]["destructive"] is True
    assert is_destructive("upload_record") is True
    assert TOOLS_REGISTRY["delete_record"]["destructive"] is False
    assert is_destructive("delete_record") is False

import os
from pathlib import Path

def new_get_config_dir() -> Path:
    """Get OS-appropriate config directory."""
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "pygog"

    if os.name == "posix":
        if Path("/Library").exists(): # macOS
            return Path.home() / "Library" / "Application Support" / "pygog"

        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "pygog"
        return Path.home() / ".config" / "pygog"

    return Path.home() / ".pygog"

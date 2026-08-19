import pytest

import pygog.cli as cli
import pygog.config as config


def _reset_cli_state() -> None:
    defaults = cli.State()
    cli.state.__dict__.clear()
    cli.state.__dict__.update(defaults.__dict__)


@pytest.fixture(autouse=True)
def reset_global_state():
    _reset_cli_state()
    config._config = None
    try:
        yield
    finally:
        _reset_cli_state()
        config._config = None

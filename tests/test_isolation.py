import pygog.cli as cli
import pygog.config as config


def test_state_can_be_mutated_for_isolation_check():
    cli.state.account = "leaked@example.com"
    cli.state.client = "leaked-client"
    cli.state.json_output = True
    cli.state.plain_output = True
    cli.state.color = "never"
    cli.state.verbose = True
    cli.state.force = True
    cli.state.no_input = True
    config._config = object()


def test_state_is_reset_between_tests():
    assert cli.state.__dict__ == cli.State().__dict__
    assert config._config is None

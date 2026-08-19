"""Entry point for pygog CLI."""

from pygog.cli import app
from pygog.context import get_context
from pygog.errors import PygogError, emit_error


def main():
    """Main entry point."""
    try:
        app()
    except (KeyboardInterrupt, SystemExit):
        raise
    except PygogError as error:
        context = get_context()
        raise SystemExit(
            emit_error(
                error,
                json_output=context.json_output,
                verbose=context.verbose,
            )
        ) from error


if __name__ == "__main__":
    main()

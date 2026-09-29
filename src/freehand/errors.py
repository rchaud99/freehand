"""Expected, user-facing errors.

`FreehandError` is the base of every error the CLI reports as a one-line message instead of a traceback. The
`freehand` command's exit codes:

    0    success
    1    a check failed: `replay` found a mismatch, `validate` a schema error, `suite verify` a changed hash
    2    bad input: wrong arguments, a missing or empty run directory, an invalid config, an unknown model or suite
    3    a run or episode ended with cells that are not complete (stopped, partial or failed; see its manifest)
    130  interrupted (Ctrl-C); the run's manifest records which cells did not run

Anything else that escapes is a bug and prints a traceback.
"""
from __future__ import annotations

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE = 3
EXIT_INTERRUPTED = 130


class FreehandError(Exception):
    """An expected error with a clear message; the CLI prints it and exits with `exit_code`."""

    exit_code = EXIT_USAGE


class UsageError(FreehandError):
    """Invalid arguments or an invalid combination of them."""


class RunDirError(FreehandError):
    """A path given as a run directory is missing, is not a run, or holds no episodes."""

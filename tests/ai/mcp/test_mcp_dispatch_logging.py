"""The dispatcher logs the timing and the exception type of a command, and never its arguments."""

from __future__ import annotations


def test_no_dispatch_argument_reaches_a_log_record(caplog) -> None:
    """The dispatcher runs arbitrary `devops` command lines, and some carry a credential.

    `logger.debug("In-process dispatch %s ...", sub_args)` wrote the argument list
    verbatim, so `gh secret set NAME <token>` put that token in the log in clear text.
    CodeQL reported it as three high-severity `py/clear-text-logging-sensitive-data`
    alerts and they blocked the v0.2.22 release. Masking the values first made it worse --
    the sanitizer is not a barrier CodeQL recognises, so three alerts became six -- so
    nothing derived from the command reaches a record at all.
    """
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    secret = "ghp_A1b2C3d4E5f6G7h8I9j0"
    with caplog.at_level(logging.DEBUG):
        InProcessDispatcher().dispatch(["devops", "workspace", "-h", "--token", secret])
    assert secret not in caplog.text


def test_the_dispatch_record_still_reports_its_duration(caplog) -> None:
    """A record stripped of everything is not hygiene; the timing is why it exists."""
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    with caplog.at_level(logging.DEBUG):
        InProcessDispatcher().dispatch(["devops", "workspace", "-h"])
    assert "In-process dispatch finished in" in caplog.text


def test_a_handler_failure_reports_its_exception_type(caplog) -> None:
    """Which kind of failure occurred is the diagnostic that survives dropping the data."""
    import logging
    from unittest.mock import patch

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    dispatcher = InProcessDispatcher()
    secret = "ghp_A1b2C3d4E5f6G7h8I9j0"
    with patch("typer.testing.CliRunner.invoke", side_effect=RuntimeError(f"holding {secret}")):
        with caplog.at_level(logging.DEBUG):
            code, _ = dispatcher.dispatch(["devops", "workspace", "status"])
    assert ("RuntimeError" in caplog.text, secret not in caplog.text, code) == (True, True, 1)

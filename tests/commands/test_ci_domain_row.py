"""The `domain` row of `devops ci`: it reads the commits of the branch where a domain is configured,
and is skipped with its cause where none is (#5295)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app, get_check_spec
from devops_cli.core.process import prepare_tool_cmd
from tests.support.fakes.process import ProcessFake

runner = CliRunner()

_CAUSE = "no k8s.domain or cloudflare.domain is configured, so the row read no commit"


def _programs(process_fake: ProcessFake) -> list[str]:
    """The program of each command that the gate started, other than git."""
    return [call.argv[0] for call in process_fake.calls if call.argv[0] != "git"]


@pytest.mark.usefixtures("ci_root")
def test_the_domain_row_is_skipped_with_its_cause_when_no_domain_is_configured(
    process_fake: ProcessFake,
) -> None:
    """The config sets no domain, so the row starts no command, passes and names the cause."""
    result = runner.invoke(app, ["--only", "domain", "--check", "--no-cache"])

    said = " ".join(result.output.split())
    assert (result.exit_code, _programs(process_fake), f"[domain] skipped: {_CAUSE}" in said) == (
        0,
        [],
        True,
    )


@pytest.mark.usefixtures("ci_root")
@pytest.mark.parametrize("section", ["k8s", "cloudflare"])
def test_the_domain_row_starts_its_check_when_a_domain_is_configured(
    section: str, config: Callable[..., Path], process_fake: ProcessFake
) -> None:
    """Either setting is enough: the row starts the `main` of its module of `tests/gate`."""
    config({section: {"domain": "example.net"}})

    result = runner.invoke(app, ["--only", "domain", "--check", "--no-cache"])

    assert (result.exit_code, _programs(process_fake), process_fake.calls[-1].argv) == (
        0,
        ["uv"],
        tuple(prepare_tool_cmd(get_check_spec("domain").cmd)),
    )

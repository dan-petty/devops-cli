"""Unit tests for telemetry tag deduplication and OTel semantic convention normalization."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.core.cli import new_typer
from devops_cli.telemetry.tracer import (
    _normalize_and_deduplicate_attributes,
    get_tracer,
    reset_tracer,
)


@pytest.fixture(autouse=True)
def clean_tracer(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Capture all emitted OTel payloads."""
    reset_tracer()
    sent_payloads: list[tuple[str, dict[str, Any]]] = []
    tracer = get_tracer()
    monkeypatch.setattr(tracer, "_send_payload", lambda path, p: sent_payloads.append((path, p)))
    return sent_payloads


def test_normalize_and_deduplicate_attributes_removes_duplicate_tags() -> None:
    """Verify legacy tags are remapped and redundant duplicate tags are deleted."""
    attrs: dict[str, Any] = {
        "cli.function": "my_module.my_func",
        "cli.error": "Something went wrong",
        "cli.command": "test-cmd",
        "git.branch": "feat/my-branch",
        "subprocess.bin": "git",
    }

    _normalize_and_deduplicate_attributes(attrs)

    assert (
        "cli.function" in attrs,
        "cli.error" in attrs,
        attrs.get("code.function"),
        attrs.get("error.message"),
        attrs.get("process.command_line"),
        attrs.get("vcs.branch"),
        attrs.get("process.executable.name"),
    ) == (
        False,
        False,
        "my_module.my_func",
        "Something went wrong",
        "test-cmd",
        "feat/my-branch",
        "git",
    )


def test_traced_subcommand_records_clean_qualname(
    clean_tracer: list[tuple[str, dict[str, Any]]],
) -> None:
    """Verify that OTelTyper subcommands record actual handler function, never _lazy_proxy."""
    app = new_typer()
    sub_app = new_typer()

    @sub_app.command(name="ping")
    def ping_command() -> None:
        print("pong")

    app.add_typer(sub_app, name="network")

    runner = CliRunner()
    res = runner.invoke(app, ["network", "ping"])
    assert res.exit_code == 0

    trace_payloads = [p for path, p in clean_tracer if path == "/v1/traces"]
    assert len(trace_payloads) >= 1

    all_emitted_spans = [
        s for p in trace_payloads for s in p["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    for span in all_emitted_spans:
        attrs = {a["key"]: str(next(iter(a["value"].values()))) for a in span.get("attributes", [])}
        func = attrs.get("code.function", "")
        cli_func = attrs.get("cli.function", "")
        assert not func.endswith("_lazy_proxy")
        assert "OTelTyper.add_typer" not in func
        assert "_lazy_proxy" not in cli_func

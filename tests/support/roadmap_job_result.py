"""The result lines that the roadmap jobs logged in a test (#4845)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.roadmap.job_result import LINE_PREFIX

if TYPE_CHECKING:
    import pytest


def result_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Each `roadmap job result` line that `caplog` holds, in order."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith(LINE_PREFIX)
    ]


def result_fields(caplog: pytest.LogCaptureFixture) -> list[dict[str, str]]:
    """The fields of each `roadmap job result` line that `caplog` holds, in order, by name. The
    version, which each line ends with, is left out."""
    fields = [
        dict(field.split("=", 1) for field in line.removeprefix(LINE_PREFIX).split())
        for line in result_lines(caplog)
    ]
    for each in fields:
        each.pop("version")
    return fields

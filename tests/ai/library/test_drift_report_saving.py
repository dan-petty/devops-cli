"""`LibraryDriftAuditor.audit_workspace(save_report_path=...)`: the report file and its failures (#1329).

A report that cannot be written is logged and recorded in the report, never dropped (#961).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from devops_cli.ai.library.drift_auditor import LibraryDriftAuditor
from tests.support.library_contracts import write_demo_contract, write_demo_workspace

_SOURCE = "import demolib\ndemolib.compute(x=1)\n"
_LOGGER = "devops_cli.ai.library.drift_auditor"


def _auditor(tmp_path: Path) -> tuple[LibraryDriftAuditor, Path]:
    contracts_dir = tmp_path / "libraries"
    write_demo_contract(contracts_dir)
    return LibraryDriftAuditor(contracts_dir=contracts_dir), write_demo_workspace(tmp_path, _SOURCE)


def test_the_report_is_saved_as_json_with_its_counts(tmp_path: Path) -> None:
    auditor, workspace = _auditor(tmp_path)
    report_path = tmp_path / "reports" / "drift.json"

    report = auditor.audit_workspace(workspace, save_report_path=report_path)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert (saved["files_scanned"], saved["breaking_count"], report.save_error) == (1, 0, None)


def test_an_unwritable_report_path_is_logged_and_recorded(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    auditor, workspace = _auditor(tmp_path)
    (tmp_path / "blocker").write_text("", encoding="utf-8")
    report_path = tmp_path / "blocker" / "drift.json"

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        report = auditor.audit_workspace(workspace, save_report_path=report_path)

    assert (
        any(str(report_path) in record.getMessage() for record in caplog.records),
        bool(report.save_error),
        report.files_scanned,
        report_path.exists(),
    ) == (True, True, 1, False)


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes to a read-only file")
def test_a_read_only_report_of_an_earlier_run_is_replaced_not_kept(tmp_path: Path) -> None:
    auditor, workspace = _auditor(tmp_path)
    report_path = tmp_path / "reports" / "drift.json"
    report_path.parent.mkdir()
    report_path.write_text('{"files_scanned": 99}', encoding="utf-8")
    report_path.chmod(0o444)

    report = auditor.audit_workspace(workspace, save_report_path=report_path)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert (report.save_error, saved["files_scanned"]) == (None, 1)

"""`devops pr check-readiness` lists the review.toml suppressions a pull request touches (#1150)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.commands.pr import ChangedFile, _ChangedFilesRead, _check_pr_perimeter_changes

_REVIEW_TOML = """\
[[suppressions]]
rule = "B602"
path = "src/a.py"
reason = "The argv is a constant list"
expiry = "2099-12-31"

[[suppressions]]
rule = "B603"
path = "src/b.py"
reason = "Expired reason"
expiry = "2020-01-01"
"""


def test_a_pull_request_touching_a_suppressed_file_names_the_suppression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Of the two suppressions on the changed files, the warning names the unexpired one's rule,
    path and reason, read from the review.toml of the working directory's repository, and not
    the expired one."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.toml").write_text(_REVIEW_TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    changed = _ChangedFilesRead(
        [ChangedFile("src/a.py", "modified"), ChangedFile("src/b.py", "modified")]
    )

    _check_pr_perimeter_changes(changed)

    output = " ".join(capsys.readouterr().out.split())
    assert (
        output.count("1 review.toml suppression"),
        "B602" in output,
        "src/a.py" in output,
        "The argv is a constant list" in output,
        "B603" in output,
        "Expired reason" in output,
    ) == (1, True, True, True, False, False)


def test_a_pull_request_touching_no_suppressed_file_prints_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No warning when the changed files lie outside every suppression's path."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.toml").write_text(_REVIEW_TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    _check_pr_perimeter_changes(_ChangedFilesRead([ChangedFile("docs/notes.md", "modified")]))

    assert capsys.readouterr().out == ""

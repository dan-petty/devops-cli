"""The swallowed-failures ratchet counts sites and compares them with the ceilings (#1347, #2164).

The ratchet is the `swallowed-failures` row of `devops ci` (`tests/gate/swallowed_failures.py`).
Ruff finds the blind excepts, so these cases give the check the findings that Ruff prints, and no
test starts Ruff.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.gate import swallowed_failures as ratchet
from tests.gate.swallowed_failures import (
    SwallowedFailureSite,
    collect_ast_unread_check_false,
    evaluate_ratchet,
    format_over_ceiling_error,
    format_under_ceiling_error,
    lower_ceilings,
    save_ceilings,
    sites_from_ruff_items,
)


def test_the_findings_of_ruff_become_sites_with_path_line_and_rule(tmp_path: Path) -> None:
    """A finding of Ruff gives a site with its path in the repository, its row and its rule."""
    items = [
        {
            "filename": str(tmp_path / "src" / "a.py"),
            "location": {"row": 4},
            "code": "BLE001",
            "message": "Do not catch blind exception: `Exception`",
        }
    ]

    assert sites_from_ruff_items(items, tmp_path) == [
        SwallowedFailureSite("src/a.py", 4, "BLE001", "Do not catch blind exception: `Exception`")
    ]


def test_ratchet_flags_unread_check_false(tmp_path: Path) -> None:
    """A call with check=False whose result is never read is flagged by the AST check."""
    source_file = tmp_path / "dummy.py"
    source_file.write_text(
        "import subprocess\ndef bad():\n    subprocess.run(['echo'], check=False)\n",
        encoding="utf-8",
    )
    violations = collect_ast_unread_check_false(source_file, tmp_path)

    assert [(site.rule, site.line) for site in violations] == [("check=False", 3)]


def test_read_check_false_is_not_flagged(tmp_path: Path) -> None:
    """Calls with check=False whose result is read or returned are not flagged."""
    source_file = tmp_path / "good.py"
    source_file.write_text(
        "import subprocess\n"
        "def read_code():\n"
        "    res = subprocess.run(['echo'], check=False)\n"
        "    return res.returncode\n\n"
        "def read_out():\n"
        "    res = subprocess.run(['echo'], check=False)\n"
        "    if res.stdout:\n"
        "        pass\n\n"
        "def read_err():\n"
        "    res = subprocess.run(['echo'], check=False)\n"
        "    print(res.stderr)\n\n"
        "def returned():\n"
        "    return subprocess.run(['echo'], check=False)\n",
        encoding="utf-8",
    )

    assert collect_ast_unread_check_false(source_file, tmp_path) == []


def test_a_file_over_its_ceiling_is_named_with_each_site() -> None:
    """A file with more sites than its ceiling is reported with the line and rule of each site."""
    measured = {
        "a.py": [
            SwallowedFailureSite("a.py", 3, "S110", "pass"),
            SwallowedFailureSite("a.py", 9, "S112", "continue"),
        ]
    }
    over, under = evaluate_ratchet(measured, {"a.py": 1})

    assert (list(over), under) == (["a.py"], {})
    assert "a.py:3: S110 (pass)" in format_over_ceiling_error(over)


def test_ratchet_fails_when_file_under_ceiling_and_prints_lower_command() -> None:
    """When a file has fewer sites than its ceiling, the ratchet fails with the command."""
    over, under = evaluate_ratchet({}, {"sample.py": 2})
    message = format_under_ceiling_error(under)

    assert (
        bool(over),
        ratchet.CONST_LOWER_COMMAND in message,
        "sample.py: count fell from 2 to 0" in message,
    ) == (
        False,
        True,
        True,
    )


def test_lower_ceilings_command_updates_fixture_and_removes_zeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """lower_ceilings lowers counts, deletes entries that reach 0, and refuses on increases."""
    (tmp_path / "src").mkdir()
    found: list[SwallowedFailureSite] = [SwallowedFailureSite("src/f2.py", 4, "BLE001", "blind")]
    monkeypatch.setattr(ratchet, "collect_ruff_violations", lambda target, repo_root: list(found))
    fixture = tmp_path / "ceilings.json"
    save_ceilings(fixture, {"src/f1.py": 2, "src/f2.py": 3})

    updated = lower_ceilings(fixture, tmp_path)
    assert (updated.get("src/f1.py"), updated.get("src/f2.py")) == (None, 1)
    assert json.loads(fixture.read_text(encoding="utf-8")) == {"src/f2.py": 1}

    found.append(SwallowedFailureSite("src/f2.py", 8, "BLE001", "blind"))
    with pytest.raises(ValueError, match="Cannot lower ceilings"):
        lower_ceilings(fixture, tmp_path)

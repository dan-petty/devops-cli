"""The npm audit ignore file: its entries, the lockfiles they name and the day they expire (#6204).

`npm audit` reads no ignore file, so `.npm-audit-ignore.yaml` holds the advisories that no released
version fixes, in the form of `.trivyignore.yaml` (SECURITY.md, A Finding with No Fix).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import CONST_NPM_AUDIT_IGNORE_FILE, CONST_OSV_SCANNER_IGNORE_FILE
from devops_cli.core.dependency_audit import (
    NpmAuditIgnore,
    active_npm_ignores,
    load_npm_audit_ignores,
    load_osv_audit_ignores,
)

_OPENSPEC_LOCK = "src/devops_cli/tools_lock/openspec/package-lock.json"
_PICOMATCH = "GHSA-fc5q-39xc-vjpf"


def _ignore(
    advisory: str = _PICOMATCH,
    paths: tuple[str, ...] = (_OPENSPEC_LOCK,),
    expired_at: date = date(2026, 11, 20),
) -> NpmAuditIgnore:
    return NpmAuditIgnore(
        id=advisory,
        paths=list(paths),
        statement="picomatch ReDoS, no released fix (#6202)",
        expired_at=expired_at,
    )


@pytest.mark.parametrize(
    ("today", "active", "expired"),
    [(date(2026, 11, 19), {_PICOMATCH}, []), (date(2026, 11, 20), set(), [_PICOMATCH])],
    ids=["before-the-date", "on-the-date"],
)
def test_an_ignore_applies_until_its_expiry_date_as_trivy_reads_expired_at(
    today: date, active: set[str], expired: list[str]
) -> None:
    applied = active_npm_ignores([_ignore()], _OPENSPEC_LOCK, today)
    assert set(applied.active) == active
    assert [entry.id for entry in applied.expired] == expired


def test_an_ignore_applies_only_to_the_lockfiles_it_names() -> None:
    applied = active_npm_ignores(
        [_ignore()],
        "src/devops_cli/tools_lock/style-dictionary/package-lock.json",
        date(2026, 11, 17),
    )
    assert not applied.active
    assert not applied.expired


@pytest.mark.parametrize(
    ("entry", "error"),
    [
        ({"id": "GHSA-*", "paths": [_OPENSPEC_LOCK]}, "one advisory, never a wildcard"),
        (
            {"id": _PICOMATCH, "paths": ["src/devops_cli/tools_lock/*/package-lock.json"]},
            "each lockfile, never a wildcard",
        ),
        ({"id": _PICOMATCH, "paths": []}, "at least 1 item"),
        (
            {"id": _PICOMATCH, "paths": [_OPENSPEC_LOCK], "statement": "no fix yet"},
            "names the tracking issue",
        ),
    ],
    ids=["wildcard-id", "wildcard-path", "no-path", "no-tracking-issue"],
)
def test_an_ignore_entry_names_one_advisory_its_lockfiles_and_a_tracking_issue(
    entry: dict[str, object], error: str
) -> None:
    fields = {"statement": "no released fix (#6202)", "expired_at": "2026-11-20", **entry}
    with pytest.raises(ValidationError, match=error):
        NpmAuditIgnore.model_validate(fields)


def test_a_missing_ignore_file_ignores_nothing(tmp_path: Path) -> None:
    assert load_npm_audit_ignores(tmp_path / CONST_NPM_AUDIT_IGNORE_FILE) == ()


def test_the_ignore_file_reads_the_trivy_yaml_form(tmp_path: Path) -> None:
    path = tmp_path / CONST_NPM_AUDIT_IGNORE_FILE
    path.write_text(
        "vulnerabilities:\n"
        f"  - id: {_PICOMATCH}\n"
        "    paths:\n"
        f"      - {_OPENSPEC_LOCK}\n"
        "    statement: picomatch ReDoS, no released fix (#6202)\n"
        "    expired_at: 2026-11-20\n",
        encoding="utf-8",
    )
    assert load_npm_audit_ignores(path) == (_ignore(),)


def test_load_osv_audit_ignores_reads_osv_scanner_ignore_file(tmp_path: Path) -> None:
    path = tmp_path / CONST_OSV_SCANNER_IGNORE_FILE
    path.write_text(
        "vulnerabilities:\n"
        "  - id: GHSA-5h93-6whr-6q8j\n"
        "    paths:\n"
        "      - src/devops_cli/tools_lock/semgrep.txt\n"
        "    statement: mcp advisory (#3988)\n"
        "    expired_at: 2026-11-21\n",
        encoding="utf-8",
    )
    assert load_osv_audit_ignores(path) == (
        NpmAuditIgnore(
            id="GHSA-5h93-6whr-6q8j",
            paths=["src/devops_cli/tools_lock/semgrep.txt"],
            statement="mcp advisory (#3988)",
            expired_at=date(2026, 11, 21),
        ),
    )


def test_missing_osv_scanner_ignore_file_ignores_nothing(tmp_path: Path) -> None:
    assert load_osv_audit_ignores(tmp_path / CONST_OSV_SCANNER_IGNORE_FILE) == ()

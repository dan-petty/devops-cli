"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

`uv audit` and `osv-scanner` both exit 1 on a finding, and another non-zero status when the audit
could not run (uv exits 2 for network/usage; osv-scanner exits 127 when missing or other error codes).
osv-scanner reads its native `osv-scanner.toml` config directly for time-limited ignores (#6419).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.commands import BIN_NPM, BIN_OSV_SCANNER, BIN_UV
from devops_cli.core.dependency_audit import AuditVerdict, audit_verdict

_OSV_AUDIT = [BIN_OSV_SCANNER, "scan", "source", "--lockfile", "package-lock.json"]
_UV_AUDIT = [BIN_UV, "audit"]


@pytest.mark.parametrize(
    ("returncode", "verdict"),
    [
        (0, AuditVerdict.CLEAN),
        (1, AuditVerdict.VULNERABLE),
        (2, AuditVerdict.NOT_RUN),
        (127, AuditVerdict.NOT_RUN),
    ],
)
def test_osv_scanner_reads_its_exit_status_and_never_its_output(
    returncode: int, verdict: AuditVerdict
) -> None:
    """osv-scanner exits 1 on a finding and any other non-zero code when it could not run."""
    assert audit_verdict(_OSV_AUDIT, returncode, "output does not matter") == verdict


@pytest.mark.parametrize(
    ("returncode", "verdict"),
    [(0, AuditVerdict.CLEAN), (1, AuditVerdict.VULNERABLE), (2, AuditVerdict.NOT_RUN)],
)
def test_uv_audit_reads_its_exit_status_and_never_its_output(
    returncode: int, verdict: AuditVerdict
) -> None:
    """uv exits 1 on a finding and 2 when it could not run."""
    assert audit_verdict(_UV_AUDIT, returncode, "error message") == verdict


def test_every_command_of_the_audit_check_has_a_reading() -> None:
    for audit_cmd in get_check_spec("audit").commands:
        assert audit_verdict(audit_cmd, 1, "") in {AuditVerdict.VULNERABLE, AuditVerdict.NOT_RUN}


def test_no_custom_npm_ignore_symbol_remains() -> None:
    """The project removes custom npm ignore loaders, filters, models, messages, and constants."""
    target_files = [
        Path("src/devops_cli/core/dependency_audit.py"),
        Path("src/devops_cli/commands/ci.py"),
        Path("src/devops_cli/config/commands.py"),
        Path("src/devops_cli/config/constants.py"),
        Path("src/devops_cli/lang/en/messages.py"),
    ]
    forbidden_symbols = [
        "load_npm_audit_ignores",
        "active_npm_ignores",
        "NpmAuditIgnore",
        "AppliedIgnores",
        "npm_advisory_ids",
        "_read_npm_failure",
        "build_npm_audit_cmd",
        "npm_audit_lockfile",
        "CONST_NPM_AUDIT_IGNORE_FILE",
        "audit_ignored",
        "audit_ignore_expired",
    ]
    for file_path in target_files:
        content = file_path.read_text(encoding="utf-8")
        for sym in forbidden_symbols:
            assert sym not in content, f"{file_path} still contains {sym}"


def test_custom_ignore_files_are_absent() -> None:
    """Neither .npm-audit-ignore.yaml nor .osv-scanner-ignore.yaml exists on disk."""
    assert not Path(".npm-audit-ignore.yaml").is_file()
    assert not Path(".osv-scanner-ignore.yaml").is_file()


def test_audit_row_holds_no_npm_audit_and_audits_root_package_lock_with_osv_scanner() -> None:
    """The audit row runs no npm command and holds osv-scanner over the root package-lock.json."""
    spec = get_check_spec("audit")
    assert not any(cmd[0] == BIN_NPM for cmd in spec.commands)
    osv_cmds = [cmd for cmd in spec.commands if cmd[0] == BIN_OSV_SCANNER]
    assert len(osv_cmds) == 1
    assert "package-lock.json" in osv_cmds[0]

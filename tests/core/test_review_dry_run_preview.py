"""Tests for review dry-run child process isolation (#1430)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.core.process import DEFAULT_ALLOWED_ENV_VARS, run_subprocess
from devops_cli.dry_run.state import set_dry_run


def test_review_dry_run_starts_no_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run execution starts no gh process."""
    spawned_cmds: list[list[str]] = []

    from devops_cli.core import process as proc_module

    real_run = proc_module.DefaultProcessRunner.run

    def record_run(self: Any, cmd: Any, *args: Any, **kwargs: Any) -> Any:
        full_cmd = list(cmd)
        spawned_cmds.append(full_cmd)
        if full_cmd and full_cmd[0] == "gh":
            pytest.fail(f"Dry run should start no gh, but spawned: {full_cmd}")
        return real_run(self, cmd, *args, **kwargs)

    monkeypatch.setattr(proc_module.DefaultProcessRunner, "run", record_run)
    proc_module.reset_github_token()
    set_dry_run(True)
    try:
        proc = run_subprocess(["git", "status"], check=False)
        assert proc.returncode == 0
        assert not any(cmd and cmd[0] == "gh" for cmd in spawned_cmds)
    finally:
        set_dry_run(False)
        proc_module.reset_github_token()


def test_default_allowed_env_vars_preserves_session_bus_isolation() -> None:
    """Sanitized subprocess environment preserves XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS."""
    assert "XDG_RUNTIME_DIR" in DEFAULT_ALLOWED_ENV_VARS
    assert "DBUS_SESSION_BUS_ADDRESS" in DEFAULT_ALLOWED_ENV_VARS

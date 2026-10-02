"""Test suite for invalidating impossible None-dereference findings during verification."""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
import threading
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.verification import (
    _check_none_dereference_hallucination,
    _module_typechecks_clean,
)
from devops_cli.ai.review_schema import Finding

_REPOSITORY = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clear_typecheck_cache() -> None:
    """The probe is cached on path and mtime; tests must not share verdicts."""
    _module_typechecks_clean.cache_clear()


def _finding(title: str, description: str = "", location: str = "a.py:1-2") -> Finding:
    """Build a candidate finding."""
    return Finding(severity="CRITICAL", location=location, title=title, description=description)


def _typecheck(clean: bool) -> Any:  # type: ignore[valid-type]
    """Patch the type-check probe to report a verdict."""
    return patch("devops_cli.ai.review.verification._module_typechecks_clean", return_value=clean)


@pytest.fixture
def module(tmp_path: Path) -> Path:
    """Provide a Python file for the finding to cite."""
    path = tmp_path / "module.py"
    path.write_text("value: str = ''\n", encoding="utf-8")
    return path


# =============================================================================
# Invalidation
# =============================================================================


def test_a_none_dereference_claim_is_invalidated_when_the_module_typechecks(
    module: Path,
) -> None:
    """The defect this exists for: two such findings shipped as VERIFIED at 0.94 confidence.

    `mypy --strict` rejects exactly this defect, so a module that passes cannot contain it.
    """
    finding = _finding("AttributeError when dashboard.uid is None in _check_identity")
    with _typecheck(True):
        result = _check_none_dereference_hallucination(finding, module)
    assert result is not None
    assert (result.status, result.verified, result.reportable) == ("INVALIDATED", False, False)


def test_the_invalidation_reason_names_the_oracle(module: Path) -> None:
    """A reader should be able to re-run the check that dismissed their finding."""
    with _typecheck(True):
        result = _check_none_dereference_hallucination(
            _finding("NoneType has no attribute"), module
        )
    assert result is not None
    assert "mypy --strict" in result.invalidation_reason


@pytest.mark.parametrize(
    "title",
    [
        "AttributeError when panel.datasource is None",
        "NoneType object has no attribute 'strip'",
        "Possible None dereference in _check_targets",
        "Null pointer when config is none",
    ],
)
def test_each_phrasing_of_the_claim_is_recognised(title: str, module: Path) -> None:
    """Findings describe this defect several ways; recognising one spelling is not enough."""
    with _typecheck(True):
        assert _check_none_dereference_hallucination(_finding(title), module) is not None


def test_the_claim_is_recognised_in_the_description(module: Path) -> None:
    """The title is often a summary; the mechanism is stated in the description."""
    finding = _finding(
        "Unsafe attribute access", "This raises AttributeError when the value is None"
    )
    with _typecheck(True):
        assert _check_none_dereference_hallucination(finding, module) is not None


# =============================================================================
# Non-Interference
# =============================================================================


def test_a_module_that_does_not_typecheck_leaves_the_finding_alone(module: Path) -> None:
    """The oracle only speaks when it is clean.

    If mypy cannot check the module for any reason, nothing has been disproved and the
    finding must reach the model verifier exactly as before.
    """
    with _typecheck(False):
        assert (
            _check_none_dereference_hallucination(_finding("AttributeError on None"), module)
            is None
        )


def test_an_unrelated_finding_is_untouched(module: Path) -> None:
    """A clean type check says nothing about SQL injection or a missing bound."""
    with _typecheck(True):
        result = _check_none_dereference_hallucination(
            _finding("SQL injection via unparameterised query"), module
        )
    assert result is None


def test_a_non_python_file_is_untouched(tmp_path: Path) -> None:
    """mypy decides nothing about YAML."""
    path = tmp_path / "workflow.yml"
    path.write_text("on: push\n", encoding="utf-8")
    with _typecheck(True):
        assert (
            _check_none_dereference_hallucination(_finding("AttributeError on None"), path) is None
        )


def test_a_missing_file_is_untouched(tmp_path: Path) -> None:
    """A finding citing a file that does not exist is a different problem."""
    with _typecheck(True):
        result = _check_none_dereference_hallucination(
            _finding("AttributeError on None"), tmp_path / "absent.py"
        )
    assert result is None


# =============================================================================
# The Probe
# =============================================================================


def test_the_probe_reports_clean_only_on_success() -> None:
    """A non-zero exit means mypy found something, so nothing is disproved."""
    with patch("devops_cli.core.process.run_subprocess", return_value=MagicMock(returncode=1)):
        assert _module_typechecks_clean("/tmp/a.py", 1.0) is False


def test_the_probe_treats_its_own_failure_as_inconclusive() -> None:
    """A missing or hung mypy must not silently invalidate real findings."""
    with patch("devops_cli.core.process.run_subprocess", side_effect=OSError("mypy missing")):
        assert _module_typechecks_clean("/tmp/b.py", 1.0) is False


def test_the_probe_is_cached_per_file_and_modification_time() -> None:
    """Verification examines many findings against the same few files.

    Type checking once per finding would dominate the run.
    """
    with patch(
        "devops_cli.core.process.run_subprocess", return_value=MagicMock(returncode=0)
    ) as run:
        _module_typechecks_clean("/tmp/c.py", 5.0)
        _module_typechecks_clean("/tmp/c.py", 5.0)
        _module_typechecks_clean("/tmp/c.py", 6.0)
    assert run.call_count == 2


def _probe_call(cmd: list[str], cwd: Path | None) -> dict[str, Any]:
    """What a probe handed the subprocess layer, read while its temporary files still exist."""
    config = Path(cmd[cmd.index("--config-file") + 1]) if "--config-file" in cmd else None
    cache = Path(cmd[cmd.index("--cache-dir") + 1]) if "--cache-dir" in cmd else None
    return {
        "cmd": cmd,
        "cwd": Path(cwd or os.getcwd()).resolve(),
        "config": config.resolve() if config else None,
        "config_text": config.read_text(encoding="utf-8") if config else None,
        "cache": cache.resolve() if cache else None,
    }


def _plugins(config_text: str | None) -> list[str]:
    """The plugins a mypy ini file loads."""
    parser = configparser.ConfigParser()
    parser.read_string(config_text or "")
    return [p.strip() for p in parser.get("mypy", "plugins", fallback="").split(",") if p.strip()]


def test_the_probe_runs_this_interpreters_mypy_away_from_the_target(tmp_path: Path) -> None:
    """The cited module belongs to the tree under review, which is untrusted (#946).

    `uv run mypy` synced the target's project and ran its build backend, and mypy read the
    config and plugins of the directory it started in. The probe runs this interpreter's mypy
    in isolated mode, from a temporary directory it removes afterwards. Its config is
    devops-cli's own: an empty one dropped the pydantic plugin, and devops-cli modules that pass
    the project's `mypy --strict`, such as `ai/review/pipeline.py`, failed the probe.
    """
    target = tmp_path / "target"
    module = target / "module.py"
    calls: list[dict[str, Any]] = []

    def run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(_probe_call(cmd, kwargs.get("cwd")))
        return MagicMock(returncode=0)

    with patch("devops_cli.core.process.run_subprocess", side_effect=run):
        clean = _module_typechecks_clean(str(module), 1.0)

    [call] = calls
    config_arg = call["cmd"][call["cmd"].index("--config-file") + 1] if call["config"] else None
    cache_arg = call["cmd"][call["cmd"].index("--cache-dir") + 1] if call["cache"] else None
    project = tomllib.loads((_REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    assert (
        clean,
        call["cmd"],
        _plugins(call["config_text"]),
        call["config"].parent == call["cwd"] if call["config"] else None,
        call["cwd"].is_relative_to(target),
        call["cwd"].exists(),
    ) == (
        True,
        [
            sys.executable,
            "-I",
            "-m",
            "mypy",
            "--strict",
            "--config-file",
            config_arg,
            "--cache-dir",
            cache_arg,
            str(module),
        ],
        project["tool"]["mypy"]["plugins"],
        True,
        False,
        False,
    )


def test_the_probe_keeps_mypys_cache_in_devops_clis_cache_directory(
    tmp_path: Path, isolate_data_dir: Path
) -> None:
    """A cold `mypy --strict` pass over a devops-cli module's imports took up to three minutes
    on a loaded machine, past the probe's 120 s timeout, and the cache died with the temporary
    directory (#946). It lives in devops-cli's cache directory instead, one per interpreter,
    shared by every probe.
    """
    calls: list[dict[str, Any]] = []

    def run(cmd: list[str], **kwargs: Any) -> MagicMock:
        calls.append(_probe_call(cmd, kwargs.get("cwd")))
        return MagicMock(returncode=0)

    with patch("devops_cli.core.process.run_subprocess", side_effect=run):
        _module_typechecks_clean(str(tmp_path / "a.py"), 1.0)
        _module_typechecks_clean(str(tmp_path / "b.py"), 1.0)
        with patch.object(sys, "executable", str(tmp_path / "other" / "python")):
            _module_typechecks_clean(str(tmp_path / "a.py"), 2.0)

    first, second, other = (call["cache"] for call in calls)
    assert (
        "--no-incremental" in calls[0]["cmd"],
        first.parent == isolate_data_dir / "cache" / "typecheck-probe",
        first == second,
        other.parent == first.parent and other != first,
        first.is_relative_to(calls[0]["cwd"]),
    ) == (False, True, True, True, False)


def test_one_probe_runs_at_a_time(tmp_path: Path) -> None:
    """Concurrent verification workers each made the same cold pass over shared imports; one
    at a time, the first warms the cache for the rest (#946)."""
    lock = threading.Lock()
    running = [0, 0]  # now, most at once

    def run(cmd: list[str], **kwargs: Any) -> MagicMock:
        with lock:
            running[0] += 1
            running[1] = max(running)
        time.sleep(0.02)
        with lock:
            running[0] -= 1
        return MagicMock(returncode=0)

    with (
        patch("devops_cli.core.process.run_subprocess", side_effect=run),
        ThreadPoolExecutor(max_workers=4) as pool,
    ):
        verdicts = list(
            pool.map(lambda n: _module_typechecks_clean(str(tmp_path / f"{n}.py"), 1.0), range(4))
        )
    assert (verdicts, running[1]) == ([True] * 4, 1)


# Prints where `-m mypy` would import mypy from, in the interpreter the probe starts.
_WHERE_MYPY_IMPORTS_FROM = "import importlib.util; print(importlib.util.find_spec('mypy').origin)"


def _hostile_repository(root: Path, marker: Path) -> Path:
    """A repository whose build backend, mypy plugin, shadowing `mypy` package and
    `sitecustomize` each write `marker` when run: what `uv run`, mypy's config lookup, and
    `python -m` from inside it or with a `PYTHONPATH` naming it run."""
    write_marker = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n"
    for rel in (
        "backend.py",
        "plugin.py",
        "mypy/__init__.py",
        "mypy/__main__.py",
        "sitecustomize.py",
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(write_marker, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "hostile"\nversion = "0"\n\n'
        '[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n\n'
        '[tool.mypy]\nplugins = ["plugin"]\n',
        encoding="utf-8",
    )
    (root / "mypy.ini").write_text("[mypy]\nplugins = plugin\n", encoding="utf-8")
    (root / "module.py").write_text("value: str = ''\nprint(value.upper())\n", encoding="utf-8")
    return root / "module.py"


def test_a_review_started_inside_a_hostile_repository_runs_nothing_of_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reproduction from #946, checked where the process is started rather than by running
    `uv sync`: every way the repository's code could run goes through the command, its working
    directory, its config or its environment, and none of them reaches the repository.

    The CLI is started inside the repository, with the shell's `PWD`, a `MYPYPATH` and a
    `PYTHONPATH` naming it, as a devcontainer, direnv or an IDE sets for the project in hand.
    The subprocess layer passes `PYTHONPATH` on, so the probe's interpreter is started for real,
    with its flags, environment and directory, to show where it would import mypy from and that
    the repository's `sitecustomize` does not run. Without `-I` it imported the repository's.
    """
    target, marker = tmp_path / "target", tmp_path / "ran"
    module = _hostile_repository(target, marker)
    monkeypatch.chdir(target)
    monkeypatch.setenv("PWD", str(target))
    monkeypatch.setenv("MYPYPATH", str(target))
    monkeypatch.setenv("PYTHONPATH", str(target))
    calls: list[dict[str, Any]] = []
    run_for_real = subprocess.run

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "mypy" in cmd:
            interpreter = cmd[: cmd.index("-m")]
            where = run_for_real(
                [*interpreter, "-c", _WHERE_MYPY_IMPORTS_FROM],
                cwd=kwargs["cwd"],
                env=kwargs["env"],
                capture_output=True,
                text=True,
                check=True,
            )
            calls.append(
                {
                    **_probe_call(cmd, kwargs.get("cwd")),
                    "env": kwargs.get("env") or {},
                    "mypy": Path(where.stdout.strip()).resolve(),
                }
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    # Only the probe: the patch is process-wide, and the standard library starts `uname` once.
    with patch("devops_cli.core.process.subprocess.run", side_effect=run):
        result = _check_none_dereference_hallucination(
            _finding("AttributeError when value is None", location="module.py:2"), module
        )

    [call] = calls
    assert (
        result is not None,
        call["cmd"][:4],
        call["cwd"].is_relative_to(target),
        call["config"].is_relative_to(target) if call["config"] else None,
        call["cache"].is_relative_to(target) if call["cache"] else None,
        _plugins(call["config_text"]),
        sorted(name for name, value in call["env"].items() if str(target) in value),
        call["mypy"].is_relative_to(target),
        marker.exists(),
    ) == (
        True,
        [sys.executable, "-I", "-m", "mypy"],
        False,
        False,
        False,
        ["pydantic.mypy"],
        ["PYTHONPATH"],
        False,
        False,
    )


def test_the_checker_is_registered_in_the_verification_pipeline() -> None:
    """An unregistered check invalidates nothing.

    Asserted because the whole point is that it runs before the model verifier.
    """
    import inspect

    from devops_cli.ai.review import verification

    source = inspect.getsource(verification._check_code_file_hallucinations)
    assert "_check_none_dereference_hallucination" in source

"""The binary digest that the record of a review tool run holds (#1984).

A Python review tool, such as Bandit or Semgrep, starts from a launcher script that its installer
writes from a console script of the distribution. The launcher holds a few lines and the path of
an interpreter, so it does not show which code ran. The record names the installed distribution
that wrote the launcher: the digest covers each file that the `RECORD` of the distribution lists
with its hash, less the launcher scripts, and the version is the version of that distribution. A
native binary keeps the digest of its file.

Each test installs a tool into an environment under `tmp_path` as an installer does, with the
layout of `sysconfig`, and puts it on PATH. No test starts a tool.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import sysconfig
from pathlib import Path

import pytest

from devops_cli.review.canary import clear_canary_cache, resolve_tool_version_and_sha
from devops_cli.tools_lock import load_tools_lock

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def _launcher(interpreter: str, module: str) -> bytes:
    """A console script launcher as an installer writes it, for `interpreter`."""
    return (
        f"#!{interpreter}\n# -*- coding: utf-8 -*-\nimport sys\nfrom {module} import main\n"
        'if __name__ == "__main__":\n    sys.exit(main())\n'
    ).encode()


def _record_row(path: str, data: bytes) -> str:
    """The `RECORD` row of a file: its path, the urlsafe base64 of its SHA-256 and its size."""
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{path},sha256={digest},{len(data)}"


def _install(
    prefix: Path,
    name: str,
    version: str,
    *,
    package: dict[str, bytes],
    program: bytes,
    console_script: bool = True,
    record: bool = True,
) -> Path:
    """Install the distribution `name` into the environment at `prefix`, as an installer does.

    `package` holds the files of the distribution by their path in the import directory. The
    program `name` goes to the scripts directory: a launcher that the installer writes from a
    console script, or with `console_script` false a file that the distribution ships, as Ruff
    ships its binary. Without `record`, the distribution has no `RECORD`. Answers the program.
    """
    layout = {"base": str(prefix), "platbase": str(prefix)}
    site = Path(sysconfig.get_path("purelib", "venv", vars=layout))
    scripts = Path(sysconfig.get_path("scripts", "venv", vars=layout))
    dist_info = f"{name}-{version}.dist-info"
    files = {
        **package,
        f"{dist_info}/METADATA": f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n".encode(),
        f"{dist_info}/entry_points.txt": (
            f"[console_scripts]\n{name} = {name}.cli:main\n".encode() if console_script else b""
        ),
    }
    for path, data in files.items():
        (site / path).parent.mkdir(parents=True, exist_ok=True)
        (site / path).write_bytes(data)
    scripts.mkdir(parents=True, exist_ok=True)
    launcher = scripts / name
    launcher.write_bytes(program)
    launcher.chmod(0o755)
    if record:
        rows = [_record_row(path, data) for path, data in files.items()]
        rows.append(_record_row(os.path.relpath(launcher, site), program))
        rows.append(f"{dist_info}/RECORD,,")
        (site / dist_info / "RECORD").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return launcher


def _on_path(monkeypatch: pytest.MonkeyPatch, path_dir: Path, *programs: Path) -> None:
    """Link each program into `path_dir`, as `devops install-tools` links its commands, and make
    `path_dir` the only directory on PATH."""
    path_dir.mkdir(parents=True, exist_ok=True)
    for program in programs:
        (path_dir / program.name).symlink_to(program)
    monkeypatch.setenv("PATH", str(path_dir))


def _resolve(tool: str) -> tuple[str, str]:
    """The version and the binary digest of `tool`, read again from disk."""
    clear_canary_cache()
    return resolve_tool_version_and_sha(tool)


def test_a_python_tool_digest_names_its_package_not_its_launcher_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest stays the same when only the launcher changes, as it does with the path of the
    environment, and changes when a file of the package changes."""
    prefix = tmp_path / "tools" / "bandit" / "1.9.4"
    package = {"bandit/__init__.py": b"", "bandit/cli.py": b"def main():\n    return 0\n"}
    launcher = _install(
        prefix,
        "bandit",
        "1.9.4",
        package=package,
        program=_launcher("/one/env/bin/python", "bandit.cli"),
    )
    _on_path(monkeypatch, tmp_path / "bin", launcher)
    first = _resolve("bandit")
    first_launcher = hashlib.sha256(launcher.read_bytes()).hexdigest()

    _install(
        prefix,
        "bandit",
        "1.9.4",
        package=package,
        program=_launcher("/another/env/bin/python", "bandit.cli"),
    )
    other_launcher = _resolve("bandit")

    _install(
        prefix,
        "bandit",
        "1.9.4",
        package={**package, "bandit/cli.py": b"def main():\n    return 1\n"},
        program=_launcher("/another/env/bin/python", "bandit.cli"),
    )
    other_package = _resolve("bandit")

    assert _SHA256_HEX.fullmatch(first[1])
    assert first[1] != first_launcher
    assert other_launcher == first
    assert other_package[0] == first[0] == "1.9.4"
    assert other_package[1] != first[1]


def test_a_python_tool_version_is_the_version_of_the_distribution_that_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Semgrep that is not at the version `tools.lock` pins is recorded at the version that
    runs, so the version and the digest name one distribution."""
    launcher = _install(
        tmp_path / "env",
        "semgrep",
        "1.0.0",
        package={"semgrep/__init__.py": b"", "semgrep/cli.py": b"def main():\n    return 0\n"},
        program=_launcher("/env/bin/python", "semgrep.cli"),
    )
    _on_path(monkeypatch, tmp_path / "bin", launcher)

    assert load_tools_lock().python["semgrep"].version != "1.0.0"
    assert _resolve("semgrep")[0] == "1.0.0"


def test_a_python_tool_with_no_record_has_no_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A distribution without a `RECORD` lists no hash, so its digest is `unavailable`, not the
    digest of its launcher."""
    launcher = _install(
        tmp_path / "env",
        "bandit",
        "1.9.4",
        package={"bandit/__init__.py": b""},
        program=_launcher("/env/bin/python", "bandit.cli"),
        record=False,
    )
    _on_path(monkeypatch, tmp_path / "bin", launcher)

    assert _resolve("bandit") == ("1.9.4", "unavailable")


def test_a_native_binary_digest_is_the_digest_of_its_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """kube-linter is one binary, and the Ruff distribution ships its binary as a file, not as
    a console script. The digest of each is the SHA-256 of that file."""
    kube_linter = tmp_path / "tools" / "kube-linter"
    kube_linter.parent.mkdir(parents=True)
    kube_linter.write_bytes(b"\x7fELF kube-linter")
    kube_linter.chmod(0o755)
    ruff = _install(
        tmp_path / "env",
        "ruff",
        "0.16.8",
        package={"ruff/__init__.py": b""},
        program=b"\x7fELF ruff",
        console_script=False,
    )
    _on_path(monkeypatch, tmp_path / "bin", kube_linter, ruff)

    assert _resolve("kube-linter") == (
        load_tools_lock().binary["kube-linter"].version,
        hashlib.sha256(b"\x7fELF kube-linter").hexdigest(),
    )
    assert _resolve("ruff")[1] == hashlib.sha256(b"\x7fELF ruff").hexdigest()

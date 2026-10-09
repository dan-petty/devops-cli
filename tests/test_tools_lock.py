"""The tools lock: every tool `devops install-tools` installs, at an exact version (#1142)."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from packaging.requirements import Requirement

from devops_cli.tools_lock import (
    LOCK_DIR,
    LOCK_FILENAME,
    load_tools_lock,
    tool_install_dir,
    tools_lock_digest,
)

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"

# The tools the issue names; the lock may hold more as review tools arrive.
_REQUIRED_TOOLS = {
    "kubectl",
    "kustomize",
    "helm",
    "argo",
    "argocd",
    "kubectl-argo-rollouts",
    "trivy",
    "kube-linter",
    "popeye",
    "pluto",
    "k9s",
    "gitleaks",
    "osv-scanner",
    "semgrep",
    "bandit",
}


def test_the_packaged_lock_holds_every_tool_install_tools_installs() -> None:
    """The lock loads from the package and names every tool the issue lists."""
    lock = load_tools_lock()

    assert (_REQUIRED_TOOLS - set(lock.tools()), lock.python_version) == (set(), "3.14")


def test_every_binary_build_is_an_https_url_with_a_sha256() -> None:
    """Each platform build is fetched over https and checked against a 32-byte SHA-256, and a
    tar.gz build names the archive member that is the tool."""
    builds = [
        (name, tool.format, artifact)
        for name, tool in load_tools_lock().binary.items()
        for artifact in tool.platforms.values()
    ]

    assert [
        name
        for name, archive_format, artifact in builds
        if urlsplit(artifact.url).scheme != "https"
        or len(bytes.fromhex(artifact.sha256)) != 32
        or (artifact.member is not None) != (archive_format == "tar.gz")
    ] == []


def test_every_python_tool_pins_itself_in_its_hashed_requirements() -> None:
    """Each Python tool's requirements file exists and pins the tool at its locked version."""
    tools = load_tools_lock().python

    assert [
        name
        for name, tool in tools.items()
        if f"{name}=={tool.version}" not in (LOCK_DIR / tool.requirements).read_text().split()
        or "--hash=sha256:" not in (LOCK_DIR / tool.requirements).read_text()
    ] == []


def test_semgrep_links_the_pysemgrep_it_runs() -> None:
    """`semgrep` runs the `pysemgrep` it finds on PATH, so the locked Semgrep links both and
    replaces a `pysemgrep` an older Semgrep left there."""
    assert {"semgrep", "pysemgrep"} <= set(load_tools_lock().python["semgrep"].commands)


def test_the_locked_bandit_is_the_projects_own_dev_bandit() -> None:
    """The review runs the Bandit the project's own CI runs."""
    dev = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    bandit = next(Requirement(spec) for spec in dev if Requirement(spec).name == "bandit")

    assert str(bandit.specifier) == f"=={load_tools_lock().python['bandit'].version}"


def test_the_digest_covers_the_lock_and_its_requirements_files(tmp_path: Path) -> None:
    """One more byte in the lock or in a requirements file changes the digest."""
    copy = tmp_path / "lock"
    shutil.copytree(LOCK_DIR, copy)
    digests = [tools_lock_digest(copy)]
    for name in (LOCK_FILENAME, load_tools_lock().python["bandit"].requirements):
        path = copy / name
        path.write_text(path.read_text(encoding="utf-8") + "#", encoding="utf-8")
        digests.append(tools_lock_digest(copy))

    assert (len(digests[0]), digests[0] == tools_lock_digest(), len(set(digests))) == (16, True, 3)


def test_a_tool_installs_under_the_user_data_root(isolate_user_data_root: Path) -> None:
    """Each tool version has its own directory under the user-level data root."""
    assert tool_install_dir("gitleaks", "1.0.0") == isolate_user_data_root / "tools/gitleaks/1.0.0"

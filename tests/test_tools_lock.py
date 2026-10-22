"""The tools lock: every tool `devops install-tools` installs, at an exact version (#1142)."""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from packaging.requirements import Requirement
from pydantic import ValidationError

from devops_cli.tools_lock import (
    LOCK_DIR,
    LOCK_FILENAME,
    NpmTool,
    installed_commands,
    load_tools_lock,
    tool_install_dir,
    tools_lock_digest,
)
from tests.support.paths import REPO_ROOT

_PYPROJECT = REPO_ROOT / "pyproject.toml"

# The tools the issue names; the lock may hold more as review tools arrive.
_REQUIRED_TOOLS = {
    "kubectl",
    "kustomize",
    "helm",
    "argo",
    "argocd",
    "cloudflared",
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
    "openspec",
    "devcontainers-cli",
    "gh-dash",
}


def test_the_packaged_lock_holds_every_tool_install_tools_installs() -> None:
    """The lock loads from the package and names every tool the issue lists."""
    lock = load_tools_lock()

    assert (_REQUIRED_TOOLS - set(lock.tools()), lock.python_version) == (set(), "3.14")


def test_every_binary_build_is_an_https_url_with_a_sha256() -> None:
    """Each platform build is fetched over https and checked against a 32-byte SHA-256, and a
    tar.gz build names the archive member that is the tool."""
    builds = [
        (name, tool.format_of(artifact), artifact)
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


# ── Node tools ────────────────────────────────────────────────────────────────


def _npm_project_file(name: str, filename: str) -> dict[str, Any]:
    """The JSON of `filename` in the directory beside the lock that holds Node tool `name`'s
    `package.json` and `package-lock.json`."""
    parsed: dict[str, Any] = json.loads((LOCK_DIR / name / filename).read_text(encoding="utf-8"))
    return parsed


def test_the_lock_holds_openspec_as_a_node_tool_at_its_exact_pin() -> None:
    """OpenSpec is a Node tool, and its command is the link npm makes in `.bin`."""
    openspec = load_tools_lock().npm["openspec"]

    assert (openspec.version, openspec.bin, openspec.commands) == (
        "1.14.3",
        "openspec",
        ("openspec",),
    )


def test_the_lock_holds_the_dev_containers_cli_as_a_node_tool_at_its_exact_pin() -> None:
    """The Dev Containers CLI that builds the published devcontainer image is a Node tool, so
    the image build and a developer run the same CLI, and `devops ci` audits its lockfile
    (#1895)."""
    cli = load_tools_lock().npm["devcontainers-cli"]

    assert (cli.version, cli.bin, cli.commands, cli.source) == (
        "0.89.0",
        "devcontainer",
        ("devcontainer",),
        "https://github.com/devcontainers/cli",
    )


def test_a_node_tool_rejects_a_key_the_lock_does_not_define() -> None:
    """A typo in the lock fails the load rather than being ignored."""
    with pytest.raises(ValidationError, match="extra"):
        NpmTool.model_validate(
            {
                "version": "1.0.0",
                "description": "A Node tool under test",
                "source": "https://example.com/mytool",
                "bin": "mytool",
                "requirements": "mytool.txt",
            }
        )


def test_every_node_tool_depends_on_nothing_but_its_exact_pin() -> None:
    """`package.json` names one dependency at the version `tools.lock` pins, with no range, and
    the lockfile resolved that dependency to the same version."""
    tools = load_tools_lock().npm
    manifests = {name: _npm_project_file(name, "package.json")["dependencies"] for name in tools}
    resolved = {
        name: _npm_project_file(name, "package-lock.json")["packages"][f"node_modules/{package}"][
            "version"
        ]
        for name, dependencies in manifests.items()
        for package in dependencies
    }

    assert (
        {name: list(dependencies.values()) for name, dependencies in manifests.items()},
        resolved,
    ) == (
        {name: [tool.version] for name, tool in tools.items()},
        {name: tool.version for name, tool in tools.items()},
    )


def test_every_node_lockfile_is_version_3_with_a_sha512_for_each_registry_package() -> None:
    """`npm ci` checks the sha512 of every package it installs, so a package without one, one
    fetched from anywhere but the npm registry over https, or one that runs a script when it
    installs fails this check."""
    lockfiles = {
        name: _npm_project_file(name, "package-lock.json") for name in load_tools_lock().npm
    }
    packages = {
        (name, path): entry
        for name, lockfile in lockfiles.items()
        for path, entry in lockfile["packages"].items()
        if path
    }

    assert (
        {name: lockfile["lockfileVersion"] for name, lockfile in lockfiles.items()},
        bool(packages),
        [
            where
            for where, entry in packages.items()
            if not str(entry.get("integrity")).startswith("sha512-")
            or urlsplit(str(entry.get("resolved"))).scheme != "https"
            or urlsplit(str(entry.get("resolved"))).hostname != "registry.npmjs.org"
            or entry.get("hasInstallScript")
        ],
    ) == ({"openspec": 3, "devcontainers-cli": 3}, True, [])


def test_a_node_tools_command_is_the_link_npm_makes_in_its_version_directory(
    isolate_user_data_root: Path,
) -> None:
    """`npm ci` links each `bin` of its packages into `node_modules/.bin`."""
    openspec = load_tools_lock().npm["openspec"]

    assert installed_commands("openspec", openspec) == {
        "openspec": isolate_user_data_root
        / "tools"
        / "openspec"
        / openspec.version
        / "node_modules"
        / ".bin"
        / "openspec"
    }


@pytest.mark.parametrize("filename", ["package.json", "package-lock.json"])
def test_the_digest_covers_each_node_tools_package_files(tmp_path: Path, filename: str) -> None:
    """A review ran the same tools only when the digests match, and a change to a Node tool's
    manifest or lockfile changes what `npm ci` installs."""
    copy = tmp_path / "lock"
    shutil.copytree(LOCK_DIR, copy)
    before = tools_lock_digest(copy)
    changed = copy / "openspec" / filename
    changed.write_text(changed.read_text(encoding="utf-8") + " ", encoding="utf-8")

    assert (before == tools_lock_digest(), tools_lock_digest(copy) != before) == (True, True)


def test_renovate_leaves_every_node_tool_to_a_deliberate_bump() -> None:
    """Renovate can edit neither `tools.lock` nor the files a bump regenerates, so its npm manager
    is off and a new OpenSpec is one pull request that follows the runbook in the lock's header."""
    renovate = json.loads((REPO_ROOT / ".github" / "renovate.json").read_text(encoding="utf-8"))

    assert {"matchManagers": ["npm"], "enabled": False} in renovate["packageRules"]

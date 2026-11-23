"""No branch changes an environment path while dan-petty/homelab holds the environment (#6820).

The check is a module of the `k8s` row of `devops ci` (`tests/gate/k8s_checks/environment_freeze.py`),
step 12 of `docs/HOMELAB_REPO_SWITCH.md`. git gives the changed paths, so these cases give the
check the result of the git command, and no test starts git.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.gate.k8s_checks.environment_freeze import GIT_DIFF, is_environment_path, outcome


def _diff(*paths: str) -> subprocess.CompletedProcess[bytes]:
    """The result of the git command of the check when the branch changes `paths`."""
    stdout = b"".join(f"{path}\0".encode() for path in paths)
    return subprocess.CompletedProcess(list(GIT_DIFF), 0, stdout=stdout, stderr=b"")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("k8s/llm/valkey.yaml", True, id="environment-manifest"),
        pytest.param("k8s/catalog.toml", True, id="file-at-the-root-of-k8s"),
        pytest.param("k8s/monitoring/dashboards/coredns.json", True, id="environment-dashboard"),
        pytest.param("k8s/new-app/deployment.yaml", True, id="new-environment-file"),
        pytest.param("k8s/devops/kustomization.yaml", False, id="product-base"),
        pytest.param("k8s/overlays/homelab/devops/kustomization.yaml", False, id="product-overlay"),
        pytest.param("k8s/README.md", False, id="guide-of-k8s"),
        pytest.param("k8s/llm/profiles/README.md", False, id="document-under-k8s"),
        pytest.param("src/devops_cli/cli.py", False, id="source-code"),
        pytest.param("docs/CLUSTER.md", False, id="document-outside-k8s"),
        pytest.param("k8sx/a.yaml", False, id="folder-that-starts-with-k8s"),
    ],
)
def test_an_environment_path_is_a_file_of_k8s_outside_the_product_folders(
    path: str, expected: bool
) -> None:
    """The pathspec of step 10 of the runbook, without Markdown files: a document deploys
    nothing."""
    assert is_environment_path(path) is expected


def test_a_change_to_an_environment_file_fails_and_names_homelab() -> None:
    """Each finding names the path, and the last line names the repository that holds it."""
    status, lines = outcome(_diff("docs/a.md", "k8s/llm/valkey.yaml"))

    assert (status, lines[:-1]) == (
        1,
        [
            "environment-freeze: k8s/llm/valkey.yaml is an environment path, and "
            "dan-petty/homelab holds the environment."
        ],
    )
    assert "dan-petty/homelab" in lines[-1]
    assert "(changed paths: 2, environment paths: 1)" in lines[-1]


def test_a_new_environment_file_fails() -> None:
    """The rule is by folder, so a file that the copy of homelab does not hold is refused too."""
    status, lines = outcome(_diff("k8s/new-app/deployment.yaml"))

    assert (status, lines[:-1]) == (
        1,
        [
            "environment-freeze: k8s/new-app/deployment.yaml is an environment path, and "
            "dan-petty/homelab holds the environment."
        ],
    )


def test_a_move_out_of_the_environment_fails_on_its_old_path() -> None:
    """`--no-renames` gives both paths of a move, and the old path is an environment path."""
    status, lines = outcome(_diff("k8s/devops/valkey.yaml", "k8s/llm/valkey.yaml"))

    assert (status, lines[:-1]) == (
        1,
        [
            "environment-freeze: k8s/llm/valkey.yaml is an environment path, and "
            "dan-petty/homelab holds the environment."
        ],
    )


def test_the_product_base_a_document_and_a_file_outside_k8s_pass() -> None:
    """Argo CD reads the product folders from devops-cli, and a document deploys nothing."""
    assert outcome(
        _diff(
            "k8s/devops/kustomization.yaml",
            "k8s/overlays/homelab/devops/kustomization.yaml",
            "k8s/README.md",
            "src/devops_cli/cli.py",
        )
    ) == (
        0,
        [
            "environment-freeze: the branch changes no environment path from its merge base "
            "with origin/main to HEAD (changed paths: 4)."
        ],
    )


def test_a_branch_with_no_change_passes() -> None:
    """A push to main, and the base tree of a replay, have no changed path."""
    assert outcome(_diff()) == (
        0,
        [
            "environment-freeze: the branch changes no environment path from its merge base "
            "with origin/main to HEAD (changed paths: 0)."
        ],
    )


def test_a_git_failure_fails_and_names_origin_main() -> None:
    """A check that cannot read the change does not pass."""
    done = subprocess.CompletedProcess(
        list(GIT_DIFF),
        128,
        stdout=b"",
        stderr=b"fatal: ambiguous argument 'origin/main...HEAD': unknown revision\n",
    )

    status, lines = outcome(done)

    assert status == 1
    assert len(lines) == 1
    assert "exit status 128" in lines[0]
    assert "fatal: ambiguous argument 'origin/main...HEAD'" in lines[0]
    assert "git fetch origin main" in lines[0]

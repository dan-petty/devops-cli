"""No branch changes an environment path while dan-petty/homelab holds the environment: step 12
of `docs/HOMELAB_REPO_SWITCH.md` (#6820).

Since the switch of step 11, Argo CD reads the environment from dan-petty/homelab, and only the
product folders `k8s/devops` and `k8s/overlays/homelab/devops` from this repository. A change to
another file of `k8s` thus changes nothing live, and the two copies drift apart. An environment
path is a file of the pathspec of step 10: `k8s` without the two product folders. The rule is by
folder, so a new file there is an environment path too. A Markdown file deploys nothing, and steps
12 and 15 change `k8s/README.md` in this repository, so a Markdown file is not refused.

`git diff --name-only` gives the net change of the branch from its merge base with `origin/main`,
which is the diff of a pull request. `--no-renames` gives both paths of a move. On `main`, the diff
is empty. Step 17 deletes this check with the environment files.
"""

from __future__ import annotations

import subprocess
from pathlib import PurePosixPath
from typing import Final

from tests.support.paths import REPO_ROOT

_NAME: Final[str] = "environment-freeze"
_ENVIRONMENT_ROOT: Final[PurePosixPath] = PurePosixPath("k8s")
_PRODUCT_FOLDERS: Final[tuple[PurePosixPath, ...]] = (
    PurePosixPath("k8s/devops"),
    PurePosixPath("k8s/overlays/homelab/devops"),
)
_DOCUMENT_SUFFIX: Final[str] = ".md"
_RANGE: Final[str] = "origin/main...HEAD"
# `-z` ends each path with a NUL and quotes no path.
GIT_DIFF: Final[tuple[str, ...]] = ("git", "diff", "--name-only", "--no-renames", "-z", _RANGE)
_GIT_TIMEOUT_SECONDS: Final[int] = 60
_ERROR_DETAIL_CHARACTERS: Final[int] = 256


def is_environment_path(path: str) -> bool:
    """Whether `path`, relative to the root of the repository, is an environment path."""
    file = PurePosixPath(path)
    return (
        file.is_relative_to(_ENVIRONMENT_ROOT)
        and not any(file.is_relative_to(folder) for folder in _PRODUCT_FOLDERS)
        and file.suffix != _DOCUMENT_SUFFIX
    )


def outcome(done: subprocess.CompletedProcess[bytes]) -> tuple[int, list[str]]:
    """The status of the check, 1 when it fails, and the lines that it prints, for the result
    of the git command `GIT_DIFF`."""
    if done.returncode:
        detail = done.stderr.decode("utf-8", "replace").strip()[:_ERROR_DETAIL_CHARACTERS]
        return 1, [
            f"{_NAME}: git diff {_RANGE} failed with exit status {done.returncode}: {detail}. "
            "Run `git fetch origin main` with the full history, then run the row again."
        ]
    changed = [path for path in done.stdout.decode("utf-8", "replace").split("\0") if path]
    found = sorted(path for path in changed if is_environment_path(path))
    counts = f"changed paths: {len(changed)}"
    if not found:
        return 0, [
            f"{_NAME}: the branch changes no environment path from its merge base with "
            f"origin/main to HEAD ({counts})."
        ]
    return 1, [
        *(
            f"{_NAME}: {path} is an environment path, and dan-petty/homelab holds the environment."
            for path in found
        ),
        f"{_NAME}: the branch changes an environment path ({counts}, environment paths: "
        f"{len(found)}). Since step 11 of docs/HOMELAB_REPO_SWITCH.md, Argo CD reads the "
        "environment from dan-petty/homelab, so this change changes nothing live. Make the change "
        "in a pull request of dan-petty/homelab, and remove it from this branch. Step 17 deletes "
        "these files and this check.",
    ]


def check_the_branch_changes_no_environment_path() -> None:
    """The branch changes no file of the environment that dan-petty/homelab holds."""
    done = subprocess.run(
        list(GIT_DIFF),
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    status, lines = outcome(done)
    assert not status, "\n".join(lines)

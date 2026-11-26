"""devops-cli tracks no environment file under `k8s/` (#7290).

The environment has its own repository, and this repository holds the product folder
`k8s/devops` alone. A copy of an environment file here deploys nothing, and a person or an agent
who reads or edits it reads or edits a stale copy. So under `k8s/`, git tracks only the product
folder and Markdown documents. The check reads the paths of the git index, never a manifest.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import Final

from tests.support.paths import REPO_ROOT

_PRODUCT_FOLDER: Final[PurePosixPath] = PurePosixPath("k8s/devops")
_DOCUMENT_SUFFIX: Final[str] = ".md"
_GIT_TIMEOUT_SECONDS: Final[int] = 60


def _git(repository: Path, *arguments: str) -> str:
    """The output of one git command in `repository`. No `GIT_` variable of the caller, such as
    the `GIT_DIR` of a hook, points the command at another repository."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    ).stdout


def environment_files(repository: Path) -> list[str]:
    """Each tracked file under `k8s/` that is no Markdown document and not in `k8s/devops`."""
    listed = _git(repository, "ls-files", "-z", "--", "k8s").split("\0")
    return sorted(
        name
        for name in listed
        if name
        and not (file := PurePosixPath(name)).is_relative_to(_PRODUCT_FOLDER)
        and file.suffix != _DOCUMENT_SUFFIX
    )


def check_the_repository_tracks_no_environment_file() -> None:
    """Under `k8s/`, git tracks only the product folder `k8s/devops` and Markdown documents."""
    found = environment_files(REPO_ROOT)
    assert not found, (
        f"{found}: this repository holds no environment file. Under k8s/, only {_PRODUCT_FOLDER} "
        "and Markdown documents are tracked; make the change in the environment repository."
    )


def check_the_structure_rule_names_each_tracked_file_outside_the_product_folder(
    tmp_path: Path,
) -> None:
    """A tracked file elsewhere under `k8s/` is named, also in a folder whose name starts as the
    product folder's does. A product file, a document and a file that git does not track are
    not."""
    tracked = (
        "k8s/devops/service.yaml",
        "k8s/devops/dashboards/example.json",
        "k8s/README.md",
        "k8s/llm/README.md",
        "k8s/llm/values.yaml",
        "k8s/devops-copy/service.yaml",
        "k8s/catalog.toml",
        "docs/example.yaml",
    )
    for name in (*tracked, "k8s/untracked.yaml"):
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("example\n", encoding="utf-8")
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "add", "--force", "--", *tracked)

    assert environment_files(tmp_path) == [
        "k8s/catalog.toml",
        "k8s/devops-copy/service.yaml",
        "k8s/llm/values.yaml",
    ]
